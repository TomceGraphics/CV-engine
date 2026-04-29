#!/usr/bin/env python3
"""
html_to_pdf.py — Advanced HTML to PDF converter
Uses Playwright + Chromium for pixel-perfect rendering with embedded links.

Usage:
  python html_to_pdf.py input.html [options]

Examples:
  python html_to_pdf.py cv.html
  python html_to_pdf.py cv.html --mode single --paper A4 --margin 0
  python html_to_pdf.py cv.html --mode multi --paper Letter --scale 0.9
  python html_to_pdf.py cv.html --output my_cv.pdf --dpi 300
  python html_to_pdf.py cv.html --mode single --bg --landscape
"""

import argparse
import sys
import os
from pathlib import Path


# ── PAPER SIZES (width x height in mm) ─────────────────────────────────────
PAPER_SIZES = {
    "A4":      {"width": "210mm",  "height": "297mm"},
    "A3":      {"width": "297mm",  "height": "420mm"},
    "A5":      {"width": "148mm",  "height": "210mm"},
    "Letter":  {"width": "215.9mm","height": "279.4mm"},
    "Legal":   {"width": "215.9mm","height": "355.6mm"},
    "Tabloid": {"width": "279.4mm","height": "431.8mm"},
}


def parse_margin(margin_str: str) -> dict:
    """
    Parse margin string into Playwright format.
    Accepts:
      - Single value:  "20mm"  → all sides
      - Two values:    "10mm 20mm" → top/bottom, left/right
      - Four values:   "10mm 15mm 10mm 15mm" → top right bottom left
      - "0" or "none" → no margins
    """
    s = margin_str.strip().lower()
    if s in ("0", "none", "0mm", "0px"):
        return {"top": "0", "right": "0", "bottom": "0", "left": "0"}

    parts = s.split()
    if len(parts) == 1:
        v = parts[0]
        return {"top": v, "right": v, "bottom": v, "left": v}
    elif len(parts) == 2:
        tb, lr = parts
        return {"top": tb, "right": lr, "bottom": tb, "left": lr}
    elif len(parts) == 4:
        return {"top": parts[0], "right": parts[1], "bottom": parts[2], "left": parts[3]}
    else:
        raise ValueError(f"Invalid margin format: '{margin_str}'. Use 1, 2, or 4 space-separated values.")


def build_single_page_css(scale: float) -> str:
    """
    CSS injected for single-page mode:
    Forces the entire document to fit onto one PDF page by
    scaling the body to viewport and disabling page breaks.
    """
    return f"""
    <style id="__single_page_override__">
      @page {{ size: auto; margin: 0; }}
      html, body {{
        width: 100% !important;
        height: auto !important;
        overflow: visible !important;
      }}
      * {{
        page-break-before: avoid !important;
        page-break-after: avoid !important;
        page-break-inside: avoid !important;
        break-before: avoid !important;
        break-after: avoid !important;
        break-inside: avoid !important;
      }}
    </style>
    """


def inject_css(html_content: str, css: str) -> str:
    """Inject CSS string into HTML before </head>."""
    if "</head>" in html_content:
        return html_content.replace("</head>", css + "</head>", 1)
    elif "<body" in html_content:
        # No head tag — inject before body
        idx = html_content.index("<body")
        return html_content[:idx] + f"<head>{css}</head>" + html_content[idx:]
    else:
        return css + html_content


def get_page_height_px(page, margin_top_mm: float = 0) -> float:
    """Measure the full scrollable height of the rendered page."""
    return page.evaluate("document.documentElement.scrollHeight")


def convert(
    input_path: Path,
    output_path: Path,
    mode: str = "multi",
    paper: str = "A4",
    landscape: bool = False,
    margin: str = "15mm",
    scale: float = 1.0,
    background: bool = True,
    dpi: int = 150,
    wait: int = 1000,
    header_html: str = None,
    footer_html: str = None,
    verbose: bool = False,
):
    """
    Core conversion function.

    Parameters
    ----------
    input_path   : Path to source HTML file
    output_path  : Path for output PDF
    mode         : "multi" (paginated) | "single" (one long page)
    paper        : Paper size key from PAPER_SIZES, or "custom"
    landscape    : Rotate to landscape
    margin       : CSS margin string (see parse_margin)
    scale        : Page scale factor (0.1–2.0). Useful for fitting wide layouts.
    background   : Print background colors and images
    dpi          : Approximate DPI (controls viewport width for rendering quality)
    wait         : Milliseconds to wait after page load (for web fonts / JS)
    header_html  : Optional HTML string for page header (multi mode only)
    footer_html  : Optional HTML string for page footer (multi mode only)
    verbose      : Print debug info
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    if paper not in PAPER_SIZES:
        print(f"ERROR: Unknown paper size '{paper}'. Choose from: {', '.join(PAPER_SIZES)}")
        sys.exit(1)

    margin_dict = parse_margin(margin)
    paper_dims = PAPER_SIZES[paper]

    if landscape:
        paper_dims = {"width": paper_dims["height"], "height": paper_dims["width"]}

    html_content = input_path.read_text(encoding="utf-8")

    # Resolve to absolute file:// URL so relative assets load correctly
    file_url = input_path.resolve().as_uri()

    if verbose:
        print(f"  Input:   {input_path}")
        print(f"  Output:  {output_path}")
        print(f"  Mode:    {mode}")
        print(f"  Paper:   {paper} {'(landscape)' if landscape else ''}")
        print(f"  Margin:  {margin_dict}")
        print(f"  Scale:   {scale}")
        print(f"  BG:      {background}")
        print(f"  DPI:     {dpi}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )

        # Viewport width based on paper + DPI for rendering quality
        # A4 is 210mm → at 96dpi that's ~794px; scale up for quality
        mm_to_px = dpi / 25.4
        paper_w_mm = float(paper_dims["width"].replace("mm", ""))
        paper_h_mm = float(paper_dims["height"].replace("mm", ""))
        viewport_w = max(800, int(paper_w_mm * mm_to_px))
        viewport_h = max(600, int(paper_h_mm * mm_to_px))

        context = browser.new_context(
            viewport={"width": viewport_w, "height": viewport_h},
        )
        page_obj = context.new_page()

        # Navigate to the file
        page_obj.goto(file_url, wait_until="networkidle", timeout=30000)

        # Wait for fonts and any JS to settle
        page_obj.wait_for_timeout(wait)

        if mode == "single":
            # ── SINGLE PAGE MODE ────────────────────────────────────────────
            # Measure full document height, set paper height to match
            content_height_px = get_page_height_px(page_obj)
            # Convert px back to mm (at 96dpi CSS reference, 1px = 0.2646mm)
            content_height_mm = content_height_px * 0.2646

            if verbose:
                print(f"  Content height: {content_height_px}px → {content_height_mm:.1f}mm")

            pdf_bytes = page_obj.pdf(
                width=paper_dims["width"],
                height=f"{content_height_mm:.2f}mm",
                print_background=background,
                scale=scale,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )

        else:
            # ── MULTI PAGE MODE ─────────────────────────────────────────────
            pdf_kwargs = dict(
                width=paper_dims["width"],
                height=paper_dims["height"],
                print_background=background,
                scale=scale,
                margin=margin_dict,
            )

            if header_html:
                pdf_kwargs["display_header_footer"] = True
                pdf_kwargs["header_template"] = header_html
            if footer_html:
                pdf_kwargs["display_header_footer"] = True
                pdf_kwargs["footer_template"] = footer_html or ""

            pdf_bytes = page_obj.pdf(**pdf_kwargs)

        browser.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)
    size_kb = len(pdf_bytes) / 1024
    print(f"✓ PDF saved: {output_path}  ({size_kb:.0f} KB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert HTML to PDF using Playwright + Chromium.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES
  # Standard multi-page A4 CV
  python html_to_pdf.py cv.html

  # Single-page (no page breaks, full height)
  python html_to_pdf.py cv.html --mode single

  # Letter size, 10% smaller scale, landscape
  python html_to_pdf.py cv.html --paper Letter --scale 0.9 --landscape

  # No margins, high quality
  python html_to_pdf.py cv.html --margin 0 --dpi 300

  # Custom output path
  python html_to_pdf.py cv.html --output exports/thomas_cv_2026.pdf

  # With custom header/footer (multi mode only)
  python html_to_pdf.py cv.html --header '<div style="font-size:9px;width:100%;text-align:right;padding:4px 16px;">Thomas Dukoski</div>'

  # Batch convert multiple files
  python html_to_pdf.py *.html --output-dir exports/
        """,
    )

    parser.add_argument(
        "inputs",
        nargs="+",
        help="HTML file(s) to convert. Supports glob patterns.",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output PDF path. Defaults to same name as input with .pdf extension.",
    )
    parser.add_argument(
        "--output-dir", "-d",
        default=None,
        help="Output directory for batch conversions.",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["multi", "single"],
        default="multi",
        help=(
            "multi: paginated PDF with page breaks (default). "
            "single: one continuous page matching full document height."
        ),
    )
    parser.add_argument(
        "--paper", "-p",
        choices=list(PAPER_SIZES.keys()),
        default="A4",
        help="Paper size (default: A4).",
    )
    parser.add_argument(
        "--landscape", "-l",
        action="store_true",
        help="Rotate to landscape orientation.",
    )
    parser.add_argument(
        "--margin",
        default="15mm",
        help=(
            "Page margins. Accepts 1, 2, or 4 space-separated CSS values. "
            "Examples: '20mm', '10mm 15mm', '10mm 15mm 10mm 15mm', '0'. "
            "(default: 15mm — applies to multi mode; single mode always uses 0)"
        ),
    )
    parser.add_argument(
        "--scale", "-s",
        type=float,
        default=1.0,
        help="Page scale factor 0.1–2.0 (default: 1.0). Use 0.9 to shrink wide layouts.",
    )
    parser.add_argument(
        "--bg", "--background",
        dest="background",
        action="store_true",
        default=True,
        help="Print background colors and images (default: on).",
    )
    parser.add_argument(
        "--no-bg",
        dest="background",
        action="store_false",
        help="Disable background colors and images.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Rendering quality in DPI (default: 150). Use 300 for print.",
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=1000,
        help="Milliseconds to wait after page load for fonts/JS (default: 1000).",
    )
    parser.add_argument(
        "--header",
        default=None,
        help="HTML string for page header (multi mode only).",
    )
    parser.add_argument(
        "--footer",
        default=None,
        help="HTML string for page footer (multi mode only).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed rendering info.",
    )

    args = parser.parse_args()

    # Resolve input files (handle globs from shell that didn't expand)
    import glob
    input_paths = []
    for pattern in args.inputs:
        matched = glob.glob(pattern)
        if matched:
            input_paths.extend([Path(p) for p in matched])
        else:
            input_paths.append(Path(pattern))

    if not input_paths:
        print("ERROR: No input files found.")
        sys.exit(1)

    # Determine output paths
    results = []
    for input_path in input_paths:
        if args.output and len(input_paths) == 1:
            output_path = Path(args.output)
        elif args.output_dir:
            output_path = Path(args.output_dir) / (input_path.stem + ".pdf")
        else:
            output_path = input_path.with_suffix(".pdf")

        result = convert(
            input_path=input_path,
            output_path=output_path,
            mode=args.mode,
            paper=args.paper,
            landscape=args.landscape,
            margin=args.margin,
            scale=args.scale,
            background=args.background,
            dpi=args.dpi,
            wait=args.wait,
            header_html=args.header,
            footer_html=args.footer,
            verbose=args.verbose,
        )
        results.append(result)

    if len(results) > 1:
        print(f"\n✓ Converted {len(results)} files.")


if __name__ == "__main__":
    main()
