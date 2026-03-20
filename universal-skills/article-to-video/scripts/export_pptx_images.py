"""
Export PPTX slides into JPG or PNG images.

Primary path on Windows:
    PowerPoint COM automation -> slide.Export(...)

Fallback path:
    LibreOffice PDF conversion + pdftoppm

Usage:
    python export_pptx_images.py <deck.pptx> <output_dir> [--pages 3,5-7] [--chapter methods] [--source-json slide-spec.json]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from slide_spec import load_slide_spec


def parse_page_selector(value: str, total_pages: int) -> list[int]:
    pages: set[int] = set()
    for chunk in value.split(","):
        token = chunk.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"invalid page range '{token}'")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(token))

    invalid = sorted(page for page in pages if page < 1 or page > total_pages)
    if invalid:
        raise ValueError(f"selected pages out of range: {invalid}; valid pages are 1-{total_pages}")
    return sorted(pages)


def resolve_target_pages(
    total_pages: int,
    page_selector: str | None,
    chapter_id: str | None,
    source_json: str | None,
) -> list[int] | None:
    if page_selector and chapter_id:
        raise ValueError("--pages and --chapter cannot be used together")

    if page_selector:
        return parse_page_selector(page_selector, total_pages)

    if not chapter_id:
        return None

    if not source_json:
        raise ValueError("--chapter requires --source-json slide-spec.json")

    spec = load_slide_spec(source_json)
    matched = [page["page"] for page in spec.get("pages", []) if page.get("chapter_id") == chapter_id]
    if not matched:
        raise ValueError(f"chapter_id '{chapter_id}' not found in {source_json}")
    invalid = [page for page in matched if page < 1 or page > total_pages]
    if invalid:
        raise ValueError(f"chapter '{chapter_id}' resolved to invalid pages: {invalid}")
    return matched


def count_slides_with_powerpoint(pptx_path: str) -> int | None:
    command = rf"""
$ErrorActionPreference = 'Stop'
$ppt = New-Object -ComObject PowerPoint.Application
try {{
  $presentation = $ppt.Presentations.Open('{pptx_path}', $false, $false, $false)
  try {{
    Write-Output $presentation.Slides.Count
  }} finally {{
    $presentation.Close()
  }}
}} finally {{
  $ppt.Quit()
}}
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return None


def export_with_powerpoint(
    pptx_path: str,
    output_dir: str,
    pages: list[int] | None,
    width: int,
    height: int,
    image_format: str,
) -> bool:
    ext = image_format.upper()
    pages_expr = "$null" if not pages else "@(" + ",".join(str(page) for page in pages) + ")"
    command = rf"""
$ErrorActionPreference = 'Stop'
$ppt = New-Object -ComObject PowerPoint.Application
try {{
  $presentation = $ppt.Presentations.Open('{pptx_path}', $false, $false, $false)
  try {{
    $pages = {pages_expr}
    if ($pages -eq $null) {{
      $pages = 1..$presentation.Slides.Count
    }}
    foreach ($page in $pages) {{
      $slide = $presentation.Slides.Item([int]$page)
      $target = Join-Path '{output_dir}' ('slide-{{0:D3}}.{{1}}' -f [int]$page, '{image_format}')
      $slide.Export($target, '{ext}', {width}, {height})
    }}
  }} finally {{
    $presentation.Close()
  }}
}} finally {{
  $ppt.Quit()
}}
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.stderr.strip():
        print("PowerPoint export failed, trying fallback path...", file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
    return False


def find_binary(name: str) -> str | None:
    direct = shutil.which(name)
    if direct:
        return direct

    roots = [Path("C:/Program Files"), Path("C:/Program Files (x86)")]
    matches = []
    for root in roots:
        if not root.exists():
            continue
        matches.extend(root.rglob(name))
        if matches:
            break
    return str(matches[0]) if matches else None


def export_with_libreoffice(
    pptx_path: str,
    output_dir: str,
    pages: list[int] | None,
    total_pages: int,
    image_format: str,
) -> bool:
    soffice = find_binary("soffice.exe") or find_binary("soffice")
    pdftoppm = find_binary("pdftoppm.exe") or find_binary("pdftoppm")
    if not soffice or not pdftoppm:
        return False

    with tempfile.TemporaryDirectory(prefix="pptx-export-") as temp_dir:
        pdf_path = os.path.join(temp_dir, Path(pptx_path).stem + ".pdf")
        convert = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", temp_dir, pptx_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if convert.returncode != 0 or not os.path.exists(pdf_path):
            return False

        selected_pages = pages or list(range(1, total_pages + 1))
        for page in selected_pages:
            prefix = os.path.join(output_dir, f"slide-{page:03d}")
            subprocess.run(
                [
                    pdftoppm,
                    f"-{image_format}",
                    "-r",
                    "150",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    pdf_path,
                    prefix,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            produced = prefix + "-1." + image_format
            target = prefix + "." + image_format
            if os.path.exists(produced):
                if os.path.exists(target):
                    os.unlink(target)
                os.rename(produced, target)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Export PPTX slides to images")
    parser.add_argument("pptx_path", help="input PPTX deck")
    parser.add_argument("output_dir", help="directory for slide images")
    parser.add_argument("--width", type=int, default=1920, help="export width in pixels")
    parser.add_argument("--height", type=int, default=1080, help="export height in pixels")
    parser.add_argument("--format", choices=["jpg", "png"], default="jpg", help="image format")
    parser.add_argument("--pages", default=None, help="only export selected pages, e.g. 3,5-7")
    parser.add_argument("--chapter", default=None, help="only export selected chapter_id")
    parser.add_argument("--source-json", default=None, help="slide-spec.json for resolving --chapter")
    args = parser.parse_args()

    pptx_path = os.path.abspath(args.pptx_path)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    total_pages = count_slides_with_powerpoint(pptx_path)
    if total_pages is None:
        spec = load_slide_spec(args.source_json) if args.source_json else None
        total_pages = len(spec.get("pages", [])) if spec else 0
    if total_pages <= 0:
        print("ERROR: failed to determine slide count for the PPTX deck", file=sys.stderr)
        raise SystemExit(1)

    try:
        target_pages = resolve_target_pages(total_pages, args.pages, args.chapter, args.source_json)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

    exported = export_with_powerpoint(
        pptx_path,
        output_dir,
        target_pages,
        args.width,
        args.height,
        args.format,
    )
    if not exported:
        exported = export_with_libreoffice(pptx_path, output_dir, target_pages, total_pages, args.format)

    if not exported:
        print(
            "ERROR: failed to export PPTX images. Install Microsoft PowerPoint or LibreOffice + pdftoppm.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    selected = target_pages or list(range(1, total_pages + 1))
    for page in selected:
        print(f"Exported slide-{page:03d}.{args.format}")
    print(f"Output dir: {output_dir}")


if __name__ == "__main__":
    main()
