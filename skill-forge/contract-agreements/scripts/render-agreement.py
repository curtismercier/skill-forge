#!/usr/bin/env python3
"""
Brief, Informative, Friendly, Firm
render-agreement.py — render a markdown agreement to an editable HTML preview.

Usage:
    python3 render-agreement.py path/to/agreement.md              # writes .html alongside
    python3 render-agreement.py path/to/agreement.md --open       # writes + opens in browser
    python3 render-agreement.py path/to/agreement.md --output out.html  # custom path

Features:
    - Professional contract typography (Times New Roman 12pt, print-friendly)
    - Inline editing via contenteditable on each section
    - Save button → downloads edited content as markdown
    - Print/PDF button → browser's native print-to-PDF
    - Draft watermark overlay
    - Auto-generated filename from document title
"""

import argparse
import html as html_module
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_markdown_sections(text: str) -> tuple:
    """Split markdown into editable sections by heading level."""
    lines = text.split('\n')
    sections = []
    current = {"type": "text", "content": [], "id": None}

    # Extract title from first # heading for filename
    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    doc_title = title_match.group(1).strip() if title_match else "Agreement"

    section_count = 0

    for line in lines:
        heading_match = re.match(r'^(#{1,3})\s+(.+)$', line)
        if heading_match:
            # Flush current section
            if current["content"]:
                sections.append(current)

            level = len(heading_match.group(1))
            section_count += 1
            current = {
                "type": "heading",
                "level": level,
                "text": heading_match.group(2),
                "content": [line],
                "id": f"section-{section_count}",
                "element": f"h{level}",
            }
        else:
            current["content"].append(line)

    # Flush last section
    if current["content"]:
        sections.append(current)

    return sections, doc_title


def render_markdown_to_html(markdown_text: str) -> str:
    """Convert simple markdown (the subset we use) to HTML."""
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', markdown_text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)

    # Tables
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect table: line with | and at least one --- row after
        if '|' in line and i + 1 < len(lines) and '---' in lines[i + 1]:
            headers = [h.strip() for h in line.split('|') if h.strip()]
            table_html = '<table>\n<thead>\n<tr>'
            for h in headers:
                table_html += f'<th>{html_module.escape(h)}</th>'
            table_html += '</tr>\n</thead>\n<tbody>\n'
            i += 2
            while i < len(lines) and '|' in lines[i]:
                cells = [c.strip() for c in lines[i].split('|') if c.strip()]
                table_html += '<tr>'
                for c in cells:
                    table_html += f'<td>{html_module.escape(c)}</td>'
                table_html += '</tr>\n'
                i += 1
            table_html += '</tbody>\n</table>'
            result.append(table_html)
        elif '|' in line:
            # Could be a stray pipe line or simple inline table
            result.append(line)
            i += 1
        else:
            # Horizontal rule
            if line.strip() == '---':
                result.append('<hr>')
            elif line.strip() == '':
                result.append('')
            else:
                result.append(line)
            i += 1

    text = '\n'.join(result)

    # Lists (simple unordered)
    result = []
    in_list = False
    for line in text.split('\n'):
        list_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
        if list_match:
            content = list_match.group(2)
            if not in_list:
                result.append('<ul>')
                in_list = True
            result.append(f'  <li>{content}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append(line)
    if in_list:
        result.append('</ul>')

    return '\n'.join(result)


def serialize_section(content_lines: list[str]) -> str:
    """Join content lines and render applicable markdown to HTML."""
    raw = '\n'.join(content_lines)
    return render_markdown_to_html(raw)


def generate_html(sections: list[dict], doc_title: str, source_path: str, markdown_text: str = '') -> str:
    """Generate a standalone editable HTML document."""
    # Build body content
    body_html = '<div class="contract" id="contract-document">\n'

    # Add hidden metadata
    body_html += f'<div id="doc-metadata" style="display:none;" data-source="{html_module.escape(source_path)}"></div>\n'

    for section in sections:
        if section["type"] == "heading" and section["level"] == 1:
            # Main title
            body_html += f'<h1 class="doc-title" id="{section["id"]}">{html_module.escape(section["text"])}</h1>\n'
            # Render preamble (Date, Parties, etc.) as an editable section
            preamble_lines = section["content"][1:]  # skip the heading line
            preamble_text = '\n'.join(preamble_lines).strip()
            if preamble_text:
                preamble_html = serialize_section(preamble_lines)
                body_html += (
                    f'<section class="editable-section">\n'
                    f'  <div class="section-content" contenteditable="true">{preamble_html}</div>\n'
                    f'</section>\n'
                )
        elif section["type"] == "heading":
            section_id = section["id"]
            section_text = html_module.escape(section["text"])
            content_html = serialize_section(section["content"][1:])  # skip heading line
            body_html += (
                f'<section id="{section_id}" class="editable-section">\n'
                f'  <h{section["level"]} class="section-heading">{section_text}</h{section["level"]}>\n'
                f'  <div class="section-content" contenteditable="true">{content_html}</div>\n'
                f'</section>\n'
            )
        else:
            content_html = serialize_section(section["content"])
            if content_html.strip():
                body_html += (
                    f'<section class="editable-section">\n'
                    f'  <div class="section-content" contenteditable="true">{content_html}</div>\n'
                    f'</section>\n'
                )

    # Signature section — special handling, not editable
    body_html += '</div>\n'  # close contract

    # Embed raw markdown source for save/load round-trip
    escaped_source = html_module.escape(markdown_text)
    body_html += f'<script id="raw-source" type="text/markdown">{escaped_source}</script>\n'

    # Toolbar
    toolbar = '''
<div class="toolbar">
  <span class="toolbar-title">Contract Editor</span>
  <span class="toolbar-spacer"></span>
  <span class="toolbar-status" id="status-msg">Ready</span>
  <button class="btn btn-load" onclick="document.getElementById('file-input').click()">\U0001f4c2 Load</button>
  <button class="btn btn-save" onclick="saveDocument()">\U0001f4be Save</button>
  <button class="btn btn-print" onclick="window.print()">\U0001f5a8\ufe0f Print / PDF</button>
  <button class="btn btn-reset" onclick="resetEdits()">\u21a9\ufe0f Reset</button>
  <input type="file" id="file-input" accept=".md" style="display:none" onchange="loadDocument(event)">
</div>
'''

    # JavaScript for save and edit
    js = '''
<script>
let rawSource = document.getElementById('raw-source');

function getDocumentText() {
  const contract = document.getElementById('contract-document');
  const sections = contract.querySelectorAll('section.editable-section');
  const title = document.querySelector('h1.doc-title');
  let md = '';

  if (title) {
    md += '# ' + title.textContent.trim() + '\\n\\n';
  }

  // Get preamble (before first section)
  let before = title ? title.nextElementSibling : contract.firstElementChild;
  const nodes = [];
  let current = before;
  while (current && current.tagName !== 'SECTION' && current.id !== 'raw-source' && current.tagName !== 'SCRIPT') {
    if (current.nodeType === 1 && current.id !== 'doc-metadata') nodes.push(current);
    current = current.nextElementSibling;
  }
  nodes.forEach(n => {
    md += htmlToMarkdown(n.innerHTML || n.textContent) + '\\n';
  });

  sections.forEach(s => {
    const heading = s.querySelector('.section-heading');
    const content = s.querySelector('.section-content');
    if (heading) {
      const tag = heading.tagName.toLowerCase();
      md += '\\n' + '#'.repeat(parseInt(tag[1])) + ' ' + heading.textContent.trim() + '\\n\\n';
    }
    if (content) {
      md += htmlToMarkdown(content.innerHTML) + '\\n';
    }
  });

  return md;
}

function htmlToMarkdown(html) {
  let text = html;

  // Convert <strong> to **
  text = text.replace(/<strong[^>]*>(.*?)<\\/strong>/g, '**$1**');
  text = text.replace(/<em[^>]*>(.*?)<\\/em>/g, '*$1*');

  // Convert <br> to newlines
  text = text.replace(/<br\\s*\\/?>/gi, '\\n');

  // Convert <p> to blocks
  text = text.replace(/<p[^>]*>(.*?)<\\/p>/gi, '$1\\n\\n');

  // Convert <li> to list items
  text = text.replace(/<li[^>]*>(.*?)<\\/li>/gi, '- $1\\n');

  // Tables: convert back to pipe-delimited
  text = text.replace(/<\\/thead>/gi, '');
  text = text.replace(/<thead>/gi, '');
  text = text.replace(/<\\/tbody>/gi, '');
  text = text.replace(/<tbody>/gi, '');
  text = text.replace(/<\\/tr>/gi, '|\\n');
  text = text.replace(/<tr[^>]*>/gi, '');
  text = text.replace(/<\\/th>/gi, '|');
  text = text.replace(/<th[^>]*>/gi, '| ');
  text = text.replace(/<\\/td>/gi, '|');
  text = text.replace(/<td[^>]*>/gi, '| ');

  // Strip remaining tags
  text = text.replace(/<[^>]+>/g, '');

  // Decode HTML entities
  text = text.replace(/&amp;/g, '&');
  text = text.replace(/&lt;/g, '<');
  text = text.replace(/&gt;/g, '>');
  text = text.replace(/&quot;/g, '"');
  text = text.replace(/&#39;/g, "'");
  text = text.replace(/&nbsp;/g, ' ');

  // Clean up multiple blank lines
  text = text.replace(/\\n{3,}/g, '\\n\\n');

  return text.trim();
}

function getDocTitle() {
  const title = document.querySelector('h1.doc-title');
  if (!title) return 'document';
  return title.textContent.trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function saveDocument() {
  const md = getDocumentText();
  const statusEl = document.getElementById('status-msg');
  const slug = getDocTitle();

  // Update hidden raw source for round-trip
  const rawEl = document.getElementById('raw-source');
  if (rawEl) rawEl.textContent = md;

  // Download
  const filename = slug + '-' + new Date().toISOString().slice(0, 10) + '.md';
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  statusEl.textContent = '\\u2705 Saved as ' + filename;
  setTimeout(() => { statusEl.textContent = 'Ready'; }, 3000);
}

function resetEdits() {
  if (confirm('Reset all edits to original?')) {
    location.reload();
  }
}

// --- Load / re-render from .md file ---

function loadDocument(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(e) {
    renderDocument(e.target.result);
    document.getElementById('status-msg').textContent = '\\u2705 Loaded: ' + file.name;
    setTimeout(() => {
      document.getElementById('status-msg').textContent = 'Ready';
    }, 3000);
  };
  reader.readAsText(file);

  // Reset so same file can be loaded again
  event.target.value = '';
}

function parseMarkdownSections(text) {
  const lines = text.split('\\n');
  const sections = [];
  let current = { type: 'text', content: [] };
  let sectionCount = 0;

  const titleMatch = text.match(/^#\\s+(.+)$/m);
  const docTitle = titleMatch ? titleMatch[1].trim() : 'Document';

  for (const line of lines) {
    const headingMatch = line.match(/^(#{1,3})\\s+(.+)$/);
    if (headingMatch) {
      if (current.content.length > 0) sections.push(current);
      sectionCount++;
      current = {
        type: 'heading',
        level: headingMatch[1].length,
        text: headingMatch[2],
        content: [line],
        id: 'section-' + sectionCount
      };
    } else {
      current.content.push(line);
    }
  }
  if (current.content.length > 0) sections.push(current);

  return { sections, docTitle };
}

function renderMarkdownToHTML(text) {
  let result = text.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
  result = result.replace(/\\*(.+?)\\*/g, '<em>$1</em>');

  // Tables
  const lines = result.split('\\n');
  const newLines = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.includes('|') && i + 1 < lines.length && lines[i + 1].includes('---')) {
      const headers = line.split('|').map(c => c.trim()).filter(c => c);
      let tableHtml = '<table>\\n<thead>\\n<tr>';
      headers.forEach(h => { tableHtml += '<th>' + h + '</th>'; });
      tableHtml += '</tr>\\n</thead>\\n<tbody>\\n';
      i += 2;
      while (i < lines.length && lines[i].includes('|')) {
        const cells = lines[i].split('|').map(c => c.trim()).filter(c => c);
        tableHtml += '<tr>';
        cells.forEach(c => { tableHtml += '<td>' + c + '</td>'; });
        tableHtml += '</tr>\\n';
        i++;
      }
      tableHtml += '</tbody>\\n</table>';
      newLines.push(tableHtml);
    } else {
      if (line.trim() === '---') newLines.push('<hr>');
      else newLines.push(line);
      i++;
    }
  }
  result = newLines.join('\\n');

  // Lists
  const listLines = result.split('\\n');
  const finalLines = [];
  let inList = false;
  for (const line of listLines) {
    const listMatch = line.match(/^\\s*[-*+]\\s+(.+)$/);
    if (listMatch) {
      if (!inList) { finalLines.push('<ul>'); inList = true; }
      finalLines.push('  <li>' + listMatch[1] + '</li>');
    } else {
      if (inList) { finalLines.push('</ul>'); inList = false; }
      finalLines.push(line);
    }
  }
  if (inList) finalLines.push('</ul>');

  return finalLines.join('\\n');
}

function renderDocument(markdownText) {
  const parsed = parseMarkdownSections(markdownText);
  const { sections, docTitle } = parsed;

  // Update raw source
  const rawEl = document.getElementById('raw-source');
  if (rawEl) rawEl.textContent = markdownText;

  // Update page title
  document.title = docTitle + ' \\u2014 Preview';

  // Rebuild contract body
  const contract = document.getElementById('contract-document');
  let html = '';

  for (const section of sections) {
    if (section.type === 'heading' && section.level === 1) {
      html += '<h1 class=\"doc-title\" id=\"' + section.id + '\">'
        + escapeHtml(section.text) + '</h1>\\n';
    } else if (section.type === 'heading') {
      const headingLines = section.content.slice(1).join('\\n');
      const contentHtml = renderMarkdownToHTML(headingLines);
      html += '<section id=\"' + section.id + '\" class=\"editable-section\">\\n';
      html += '  <h' + section.level + ' class=\"section-heading\">'
        + escapeHtml(section.text) + '</h' + section.level + '>\\n';
      html += '  <div class=\"section-content\" contenteditable=\"true\">'
        + contentHtml + '</div>\\n';
      html += '</section>\\n';
    } else {
      const contentHtml = renderMarkdownToHTML(section.content.join('\\n'));
      if (contentHtml.trim()) {
        html += '<section class=\"editable-section\">\\n';
        html += '  <div class=\"section-content\" contenteditable=\"true\">'
          + contentHtml + '</div>\\n';
        html += '</section>\\n';
      }
    }
  }

  contract.innerHTML = html;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}
</script>
'''


    # CSS
    css = '''
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'Times New Roman', Garamond, Georgia, serif;
    color: #1a1a1a;
    background: #f2f0eb;
    padding-top: 60px;
    padding-bottom: 40px;
  }

  .toolbar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    background: #1a1a2e;
    color: #fff;
    padding: 10px 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.15);
  }

  .toolbar-title { font-weight: 600; font-size: 15px; }
  .toolbar-spacer { flex: 1; }
  .toolbar-status { color: #8f8; font-size: 12px; }

  .btn {
    padding: 6px 16px;
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 4px;
    background: transparent;
    color: #fff;
    cursor: pointer;
    font-size: 13px;
    transition: background 0.15s;
  }
  .btn:hover { background: rgba(255,255,255,0.1); }
  .btn-save { background: #2d7d46; border-color: #2d7d46; }
  .btn-save:hover { background: #3a9d5a; }
  .btn-print { background: #2d5a7d; border-color: #2d5a7d; }
  .btn-print:hover { background: #3a7a9d; }
  .btn-reset { background: #7d2d2d; border-color: #7d2d2d; }
  .btn-load { background: #5a5a7d; border-color: #5a5a7d; }
  .btn-load:hover { background: #7a7a9d; }
  .btn-reset { background: #7d2d2d; border-color: #7d2d2d; }
  .btn-reset:hover { background: #9d3a3a; }

  .contract {
    max-width: 8.5in;
    margin: 20px auto;
    background: #fff;
    padding: 72px 80px;
    box-shadow: 0 2px 24px rgba(0,0,0,0.08);
    position: relative;
    min-height: 11in;
  }

  /* Draft watermark */
  .contract::before {
    content: "DRAFT";
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%) rotate(-30deg);
    font-size: 120px;
    font-weight: bold;
    color: rgba(200, 50, 50, 0.06);
    pointer-events: none;
    z-index: 0;
    letter-spacing: 20px;
  }

  .doc-title {
    font-size: 22px;
    font-weight: 700;
    text-align: center;
    margin-bottom: 32px;
    color: #1a1a1a;
    border-bottom: 2px solid #1a1a1a;
    padding-bottom: 16px;
  }

  h2 { font-size: 17px; margin-top: 28px; margin-bottom: 12px; }
  h3 { font-size: 15px; margin-top: 20px; margin-bottom: 8px; }

  .editable-section {
    margin-bottom: 8px;
    position: relative;
    z-index: 1;
  }

  .section-content {
    line-height: 1.8;
    font-size: 12pt;
    padding: 4px 0;
    min-height: 1em;
    outline: none;
    transition: background 0.15s;
  }

  .section-content:focus {
    background: #fffef5;
    box-shadow: 0 0 0 2px rgba(26, 26, 46, 0.08);
    border-radius: 2px;
  }

  .section-content:hover {
    background: rgba(255, 255, 200, 0.15);
    cursor: text;
  }

  .section-content table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 12pt;
  }

  .section-content th, .section-content td {
    border: 1px solid #ccc;
    padding: 8px 12px;
    text-align: left;
  }

  .section-content th {
    background: #f5f3f0;
    font-weight: 600;
  }

  .section-content ul, .section-content ol {
    margin: 8px 0;
    padding-left: 24px;
  }

  .section-content li {
    margin-bottom: 4px;
  }

  hr {
    border: none;
    border-top: 1px solid #ccc;
    margin: 24px 0;
  }

  /* Signature blocks — used within editable content for named signature blocks */
  .sig-line {
    display: flex;
    align-items: center;
    margin: 10px 0;
    font-size: 12pt;
  }

  .sig-line span:first-child {
    min-width: 90px;
    font-weight: 600;
  }

  .sig-space {
    border-bottom: 1px solid #333;
    min-width: 280px;
    padding: 0 4px;
    font-weight: normal !important;
  }

  /* Print styles */
  @media print {
    body {
      background: #fff;
      padding: 0;
      margin: 0;
    }
    .toolbar { display: none; }
    .contract {
      box-shadow: none;
      padding: 96px 80px;
      max-width: 100%;
      min-height: auto;
      margin: 0;
    }
    .contract::before { display: none; }
    .doc-title {
      margin-bottom: 36px;
    }
    .section-content:focus { background: transparent; box-shadow: none; }
    .section-content:hover { background: transparent; }
    .section-content { outline: none; }
    .editable-section { break-inside: avoid; }
  }
</style>
'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_module.escape(doc_title)} — Preview</title>
{css}
</head>
<body>
{toolbar}
{body_html}
{js}
</body>
</html>'''

    return html


def main():
    parser = argparse.ArgumentParser(
        description="Render a markdown agreement to editable HTML preview."
    )
    parser.add_argument("input", help="Path to the markdown agreement file")
    parser.add_argument("--output", "-o", help="Output HTML path (default: input path with .html)")
    parser.add_argument("--open", action="store_true", help="Open in browser after rendering")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding="utf-8")
    sections, doc_title = parse_markdown_sections(text)

    html = generate_html(sections, doc_title, str(input_path.resolve()), text)

    output_path = args.output or input_path.with_suffix(".html")
    output_path.write_text(html, encoding="utf-8")

    print(f"Rendered: {output_path}")
    print(f"  File size: {output_path.stat().st_size:,} bytes")
    print(f"  Sections: {len([s for s in sections if s['type'] == 'heading'])}")

    if args.open:
        import webbrowser
        webbrowser.open(str(output_path.resolve()))
        print("  Opened in browser")


if __name__ == "__main__":
    main()
