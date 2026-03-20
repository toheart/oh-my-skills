"""
Render slide-spec.json into a native PPTX deck through PptxGenJS.

Usage:
    python render_pptx.py <slide-spec.json> <output.pptx>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

from slide_spec import load_slide_spec, write_json


def resolve_node_path() -> str:
    env_path = os.environ.get("NODE_PATH")
    if env_path:
        return env_path

    npm_command = "npm.cmd" if os.name == "nt" else "npm"
    result = subprocess.run(
        [npm_command, "root", "-g"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    print(
        "ERROR: failed to resolve NODE_PATH. Install pptxgenjs globally with `npm install -g pptxgenjs`.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render native PPTX from slide-spec.json")
    parser.add_argument("slide_spec", help="slide-spec.json path")
    parser.add_argument("output_pptx", help="output PPTX path")
    args = parser.parse_args()

    spec = load_slide_spec(args.slide_spec)
    output_path = os.path.abspath(args.output_pptx)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    script_path = os.path.join(os.path.dirname(__file__), "render_pptx.mjs")
    env = dict(os.environ)
    env["NODE_PATH"] = resolve_node_path()

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        normalized_path = handle.name
        write_json(normalized_path, spec)

    try:
        result = subprocess.run(
            ["node", script_path, normalized_path, output_path],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        if os.path.exists(normalized_path):
            os.unlink(normalized_path)

    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)

    if result.stdout.strip():
        print(result.stdout.strip())
    print(f"Rendered PPTX: {output_path}")


if __name__ == "__main__":
    main()
