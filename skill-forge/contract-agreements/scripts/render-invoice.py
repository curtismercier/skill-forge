#!/usr/bin/env python3
"""
render-invoice.py — professional invoice editor with tabbed preview + item menu.

Usage:
    python3 render-invoice.py                           # default template
    python3 render-invoice.py path/to/invoice.md         # load existing
    python3 render-invoice.py path/to/invoice.md --open  # load + open browser

Tabs: Preview | Items (editable line-item table) | Details (from/to, terms)
Features: add/remove line items, auto-calculated totals, dual-option support,
          Load/Save as markdown, print-to-PDF.
"""

import argparse
import json
import os
import re
import sys
import webbrowser
from pathlib import Path


DEFAULT_INVOICE = """# Invoice

**Invoice #:** [INVOICE-NUMBER]
**Date:** [DATE]
**Period:** [PERIOD]

**From:**
[Your Name]
[Your Business]
[Your Contact]

**To:**
[Client Name]
[Client Business]
[Client Contact]

---

## Services

| # | Description | Hours | Rate | Amount |
|---|---|---|---|---|
| 1 | [Service description] | [hours] | [rate] | [amount] |
|   | **Total** | | | **$0.00** |

## Payment Options

**Option A — Full Amount**
$[FULL-AMOUNT]

**Option B — Settlement**
$[SETTLEMENT-AMOUNT] — [details, expiry]

## Payment Terms

| | |
|---|---|
| **Method** | [e-transfer / wire details] |
| **Due** | [terms] |
| **Interest** | [late payment terms] |

## Notes

[Legal footer, disclaimers, Offer to Settle language]
"""


def parse_invoice_markdown(text: str) -> dict:
    """Parse invoice markdown into a structured data dict."""
    lines = text.split('\n')
    data = {
        'number': '',
        'date': '',
        'period': '',
        'from_name': '',
        'from_business': '',
        'from_contact': '',
        'from_phone': '',
        'to_name': '',
        'to_client': '',
        'to_address': '',
        'to_contact': '',
        'to_phone': '',
        'items': [],
        'opt_b_label': 'Option B \u2014 Settlement',
        'opt_b_amount': '',
        'opt_b_expiry': '',
        'payment_method': '',
        'payment_due': '',
        'payment_interest': '',
        'notes': '',
    }

    current_section = None
    in_table = False

    for line in lines:
        stripped = line.strip()

        m = re.match(r'\*\*Invoice #:\*\*\s*(.+)', stripped)
        if m: data['number'] = m.group(1).strip()

        m = re.match(r'\*\*Date:\*\*\s*(.+)', stripped)
        if m: data['date'] = m.group(1).strip()

        m = re.match(r'\*\*Period:\*\*\s*(.+)', stripped)
        if m: data['period'] = m.group(1).strip()

        m = re.match(r'^## (.+)$', stripped)
        if m:
            current_section = m.group(1).strip().lower()
            in_table = False
            continue

        if current_section is None and stripped.startswith('**') and ': **' not in stripped:
            # Check for From/To blocks before section headings
            if stripped == '**From:**':
                # Read next non-blank lines as from_name, from_business, from_contact
                idx = lines.index(line)
                next_lines = []
                for j in range(idx + 1, len(lines)):
                    if lines[j].strip() and not lines[j].strip().startswith('**') and not lines[j].strip().startswith('#'):
                        next_lines.append(lines[j].strip())
                    elif lines[j].strip():
                        break
                if len(next_lines) >= 1: data['from_name'] = next_lines[0]
                if len(next_lines) >= 2: data['from_business'] = next_lines[1]
                if len(next_lines) >= 3: data['from_contact'] = next_lines[2]
                if len(next_lines) >= 4: data['from_phone'] = next_lines[3]
                continue
            if stripped == '**To:**':
                idx = lines.index(line)
                next_lines = []
                for j in range(idx + 1, len(lines)):
                    if lines[j].strip() and not lines[j].strip().startswith('**') and not lines[j].strip().startswith('#'):
                        next_lines.append(lines[j].strip())
                    elif lines[j].strip():
                        break
                if len(next_lines) >= 1: data['to_name'] = next_lines[0]
                if len(next_lines) >= 2: data['to_client'] = next_lines[1]
                if len(next_lines) >= 3: data['to_address'] = next_lines[2]
                if len(next_lines) >= 4: data['to_contact'] = next_lines[3]
                if len(next_lines) >= 5: data['to_phone'] = next_lines[4]
                continue

        if current_section == 'payment terms':
            m = re.search(r'\*\*Method\*\*\s*\|*\s*(.+)', stripped)
            if m: data['payment_method'] = m.group(1).strip().rstrip('|').strip()
            m = re.search(r'\*\*Due\*\*\s*\|*\s*(.+)', stripped)
            if m: data['payment_due'] = m.group(1).strip().rstrip('|').strip()
            m = re.search(r'\*\*Interest\*\*\s*\|*\s*(.+)', stripped)
            if m: data['payment_interest'] = m.group(1).strip().rstrip('|').strip()

        if current_section in ('services', 'services rendered'):
            if '|' in stripped and '---' not in stripped:
                cells = [c.strip() for c in stripped.split('|') if c.strip()]
                if len(cells) >= 4:
                    if cells[0] in ('#', 'Item', 'Description'):
                        in_table = True
                        continue
                    if 'total' in cells[0].lower() or cells[0] == '':
                        continue
                    if in_table:
                        item = {}
                        desc_idx = 1 if (cells[0].isdigit() or cells[0] == '') else 0
                        item['description'] = cells[desc_idx] if desc_idx < len(cells) else ''
                        item['hours'] = cells[desc_idx+1] if desc_idx+1 < len(cells) else ''
                        item['rate'] = cells[desc_idx+2] if desc_idx+2 < len(cells) else ''
                        raw_amt = cells[desc_idx+3] if desc_idx+3 < len(cells) else ''
                        item['amount'] = re.sub(r'[$,\s]', '', raw_amt)
                        data['items'].append(item)

        if current_section == 'payment options':
            m = re.match(r'\*\*Option B[^*]*\*\*\s*(.*)', stripped)
            if m:
                # Label is on this line; amount and expiry could be on next line
                pass
            # Also check for amount on its own line with $ prefix
            amt_m = re.match(r'^\$?([0-9,]+\.?[0-9]*)\s*\u2014\s*(.*)', stripped)
            if amt_m:
                data['opt_b_amount'] = amt_m.group(1).replace(',', '')
                rest = amt_m.group(2)
                exp_m = re.search(r'expir(?:y|es)?\s*(.+?)(?:\.|$)', rest, re.I)
                if exp_m: data['opt_b_expiry'] = exp_m.group(1).strip()
            # Also try just dollar-amount line
            amt_m2 = re.match(r'^\$([0-9,]+\.?[0-9]*)$', stripped)
            if amt_m2 and amt_m2.group(1).replace(',', '') not in ('', '0'):
                data['opt_b_amount'] = amt_m2.group(1).replace(',', '')

        if current_section == 'notes':
            if stripped and not stripped.startswith('#'):
                data['notes'] += stripped + '\n'

    return data


def generate_html(data: dict, source_path: str = '') -> str:
    """Generate the tabbed invoice editor HTML."""
    items_json = json.dumps(data.get('items', []))

    # Load the HTML template
    template_path = Path(__file__).parent / 'invoice-template.html'
    html = template_path.read_text(encoding='utf-8')

    # Determine if Option B section should show
    has_option_b = bool(data.get('opt_b_amount'))

    # Substitute placeholders
    placeholders = {
        'TITLE': f"Invoice Editor \u2014 {data.get('number') or 'New Invoice'}",
        'ITEMS_JSON': items_json,
        'FROM_NAME': data.get('from_name', ''),
        'FROM_BUSINESS': data.get('from_business', ''),
        'FROM_CONTACT': data.get('from_contact', ''),
        'FROM_PHONE': data.get('from_phone', ''),
        'TO_NAME': data.get('to_name', ''),
        'TO_CLIENT': data.get('to_client', ''),
        'TO_ADDRESS': data.get('to_address', ''),
        'TO_CONTACT': data.get('to_contact', ''),
        'TO_PHONE': data.get('to_phone', ''),
        'NUMBER': data.get('number', ''),
        'DATE_VAL': data.get('date', ''),
        'PERIOD': data.get('period', ''),
        'OPT_B_LABEL': data.get('opt_b_label', 'Settlement'),
        'OPT_B_AMOUNT': data.get('opt_b_amount', ''),
        'OPT_B_EXPIRY': data.get('opt_b_expiry', ''),
        'PAYMENT_METHOD': data.get('payment_method', ''),
        'PAYMENT_DUE': data.get('payment_due', ''),
        'PAYMENT_INTEREST': data.get('payment_interest', ''),
        'NOTES': data.get('notes', '').strip(),
    }

    for key, val in placeholders.items():
        html = html.replace(f'{{{key}}}', str(val))

    # Hide Options section if no Option B amount (simple invoice, no dual-option)
    if not has_option_b:
        html = html.replace(
            'id="inv-options-section"',
            'id="inv-options-section" style="display:none"'
        )

    return html


def main():
    parser = argparse.ArgumentParser(
        description="Render an invoice markdown to a tabbed editable HTML preview."
    )
    parser.add_argument("input", nargs="?", help="Path to the invoice markdown file")
    parser.add_argument("--output", "-o", help="Output HTML path")
    parser.add_argument("--open", action="store_true", help="Open in browser after rendering")
    args = parser.parse_args()

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: {input_path} not found", file=sys.stderr)
            sys.exit(1)
        text = input_path.read_text(encoding="utf-8")
        data = parse_invoice_markdown(text)
    else:
        data = parse_invoice_markdown(DEFAULT_INVOICE)

    html = generate_html(data)

    if args.output:
        output_path = Path(args.output)
    elif args.input:
        output_path = Path(args.input).with_suffix(".html")
    else:
        output_path = Path("invoice.html")

    output_path.write_text(html, encoding="utf-8")

    print(f"Rendered: {output_path}")
    print(f"  File size: {output_path.stat().st_size:,} bytes")
    print(f"  Items: {len(data.get('items', []))}")

    if args.open:
        webbrowser.open(str(output_path.resolve()))
        print("  Opened in browser")


if __name__ == "__main__":
    main()
