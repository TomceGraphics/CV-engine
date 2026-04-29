# HTML to PDF Engine

An advanced, pixel-perfect HTML to PDF converter built with Python, Playwright, and Chromium. It supports multi-page and single-page (long document) exports, custom margins, scaling, and high-DPI rendering.

## Installation

This script requires Python 3 and the `playwright` package.

1. Ensure Python 3 is installed.
2. Install Playwright:
   ```bash
   pip install playwright
   ```
3. Install the required Chromium browser binaries:
   ```bash
   playwright install chromium
   ```

## Usage

Basic usage:
```bash
python html_to_pdf.py cv.html
```
This will generate `cv.pdf` in the same directory.

### Command-Line Options

| Option | Shortcut | Default | Description |
|---|---|---|---|
| `inputs` | | | One or more HTML files to convert (supports glob patterns, e.g., `*.html`). |
| `--output` | `-o` | Same as input | Output PDF file path. |
| `--output-dir` | `-d` | | Output directory for batch conversions. |
| `--mode` | `-m` | `multi` | `multi` for paginated with page breaks. `single` for one continuous page matching full document height. |
| `--paper` | `-p` | `A4` | Paper size (A4, A3, A5, Letter, Legal, Tabloid). |
| `--landscape` | `-l` | | Rotate to landscape orientation. |
| `--margin` | | `15mm` | Page margins (1, 2, or 4 values like CSS: `20mm`, `10mm 15mm`). Single mode uses `0`. |
| `--scale` | `-s` | `1.0` | Page scale factor (0.1–2.0). Useful for fitting wide layouts (e.g., `0.9`). |
| `--bg` / `--no-bg`| | `--bg` | Print background colors and images. |
| `--dpi` | | `150` | Rendering quality. Use `300` for high-quality print exports. |
| `--wait` | | `1000` | Milliseconds to wait after page load (useful for loading web fonts or JavaScript). |
| `--header` | | | Custom HTML string for the page header (multi mode only). |
| `--footer` | | | Custom HTML string for the page footer (multi mode only). |
| `--verbose` | `-v` | | Print detailed rendering info. |

### Examples

**Standard multi-page A4 PDF:**
```bash
python html_to_pdf.py cv.html
```

**Single-page (no page breaks, full height):**
```bash
python html_to_pdf.py cv.html --mode single
```

**Letter size, 10% smaller scale, landscape:**
```bash
python html_to_pdf.py cv.html --paper Letter --scale 0.9 --landscape
```

**High quality, no margins:**
```bash
python html_to_pdf.py cv.html --margin 0 --dpi 300
```

**Custom output path:**
```bash
python html_to_pdf.py cv.html -o exports/my_cv.pdf
```

**Batch convert multiple files:**
```bash
python html_to_pdf.py templates/*.html --output-dir exports/
```

## Using the Editable CV Templates

Included in this repository are basic, Tailwind-based CV templates (`cv_template_modern_minimal.html`, `cv_template_creative_bold.html`, `cv_template_modern_glass.html`)
`cv.html` is the actual cv i personally use and it gets updated occasionally. Feel free to use it as a reference or a starting point.

These templates are designed so you don't need to write or edit HTML to update your CV. 

1. Open the `.html` file in a text editor.
2. Scroll to the very bottom to find the `<script type="application/json" id="cv-data">` section.
3. Edit the JSON object with your personal information (name, experience, skills, etc.).
4. Save the file and run the HTML to PDF engine to generate your new CV.
