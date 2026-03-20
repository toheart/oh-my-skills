"""
Build slide-spec.json from outline.json or normalize an existing slide-spec file.

Usage:
    python build_slide_spec.py <input.json> <output.json>
"""

from __future__ import annotations

import argparse
import os

from slide_spec import document_label, load_slide_spec, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or normalize slide-spec.json")
    parser.add_argument("input_json", help="outline.json or slide-spec.json")
    parser.add_argument("output_json", help="target slide-spec.json path")
    args = parser.parse_args()

    spec = load_slide_spec(args.input_json)
    output_dir = os.path.dirname(os.path.abspath(args.output_json))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    write_json(args.output_json, spec)
    print(f"Built slide-spec from {document_label(args.input_json)}")
    print(f"Pages: {len(spec.get('pages', []))}")
    print(f"Output: {os.path.abspath(args.output_json)}")


if __name__ == "__main__":
    main()
