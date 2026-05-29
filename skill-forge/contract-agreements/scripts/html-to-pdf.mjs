#!/usr/bin/env node
/**
 * html-to-pdf.mjs — convert an HTML file to a professional PDF.
 *
 * Uses Puppeteer (already installed as a dependency of md-to-pdf) to render
 * the HTML with full CSS and produce a print-quality PDF.
 *
 * Usage:
 *   node scripts/html-to-pdf.mjs path/to/file.html                    # letter, next to source
 *   node scripts/html-to-pdf.mjs path/to/file.html -o path/to/out.pdf # custom output
 *   node scripts/html-to-pdf.mjs path/to/file.html --open             # open after generation
 *
 * Options:
 *   --format   Page format: Letter (default), A4, Legal
 *   --margin   CSS margin string: "0.8in 0.7in" (default)
 *   --open     Open the generated PDF in the system viewer
 */

import { launch } from 'puppeteer';
import { createServer } from 'http';
import { readFileSync, writeFileSync } from 'fs';
import { extname, resolve, dirname, basename } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));

function serveHtml(html, port = 0) {
  return new Promise((resolve, reject) => {
    const server = createServer((req, res) => {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(html);
    });
    server.listen(port, '127.0.0.1', () => {
      resolve({ server, port: server.address().port });
    });
    server.on('error', reject);
  });
}

async function main() {
  const args = process.argv.slice(2);
  const inputIndex = args.findIndex(a => !a.startsWith('--'));
  if (inputIndex === -1) {
    console.error('Usage: node html-to-pdf.mjs path/to/file.html [--format Letter] [--margin "0.8in 0.7in"] [--open]');
    process.exit(1);
  }

  const inputPath = resolve(args[inputIndex]);
  const format = args.includes('--format') ? args[args.indexOf('--format') + 1] : 'Letter';
  const margin = args.includes('--margin') ? args[args.indexOf('--margin') + 1] : '0.8in 0.7in';
  const shouldOpen = args.includes('--open');
  const outputArg = args.includes('-o') ? args[args.indexOf('-o') + 1] : null;

  const outputPath = outputArg
    ? resolve(outputArg)
    : inputPath.replace(extname(inputPath), '.pdf');

  if (!inputPath.endsWith('.html')) {
    console.error('Input must be an .html file');
    process.exit(1);
  }

  console.log(`  Input:  ${inputPath}`);
  console.log(`  Format: ${format}`);
  console.log(`  Margin: ${margin}`);

  const html = readFileSync(inputPath, 'utf-8');
  const { server, port } = await serveHtml(html);

  try {
    const browser = await launch({ headless: true, args: ['--no-sandbox'] });
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${port}`, { waitUntil: 'networkidle0', timeout: 15000 });

    await page.pdf({
      path: outputPath,
      format,
      margin,
      printBackground: true,
      displayHeaderFooter: true,
      footerTemplate: '<div style="font-size:7.5pt;font-family:Georgia,\'Times New Roman\',serif;color:#999;width:100%;text-align:center;padding:4px 0.7in;">Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
      preferCSSPageSize: true,
    });

    await browser.close();
    server.close();

    const stats = readFileSync(outputPath).length;
    console.log(`  PDF:    ${outputPath}`);
    console.log(`  Size:   ${(stats / 1024).toFixed(0)} KB`);

    if (shouldOpen) {
      const cmd = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
      execSync(`${cmd} "${outputPath}"`);
    }
  } catch (err) {
    server.close();
    console.error('PDF generation failed:', err.message);
    process.exit(1);
  }
}

main();
