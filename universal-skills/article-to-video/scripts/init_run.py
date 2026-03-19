"""
初始化 article-to-video 的独立运行目录。

用法:
    python init_run.py "文章标题"
    python init_run.py "文章标题" --root workspace/article-to-video
    python init_run.py "文章标题" --slug my-custom-slug

输出:
    <run_dir>/meta.json
    <run_dir>/slides/
    <run_dir>/preview/
    <run_dir>/audio/
    <run_dir>/build/
    <run_dir>/output/
    <run_dir>/canvas/
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    normalized = re.sub(r"[^\w\s-]", "", lowered)
    slug = re.sub(r"[-\s]+", "-", normalized).strip("-_")
    return slug or "article-to-video"


def build_run_dir(root: str, title: str, custom_slug: str | None) -> str:
    slug = custom_slug or slugify(title)
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    return os.path.join(root, f"{slug}-{timestamp}")


def ensure_dirs(run_dir: str) -> dict:
    dirs = {
        "run_dir": run_dir,
        "slides": os.path.join(run_dir, "slides"),
        "preview": os.path.join(run_dir, "preview"),
        "audio": os.path.join(run_dir, "audio"),
        "build": os.path.join(run_dir, "build"),
        "output": os.path.join(run_dir, "output"),
        "canvas": os.path.join(run_dir, "canvas"),
    }
    for path in dirs.values():
        os.makedirs(path, exist_ok=True)
    return dirs


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化 article-to-video 的运行目录")
    parser.add_argument("title", help="文章标题或本次视频任务名")
    parser.add_argument(
        "--root",
        default="workspace/article-to-video",
        help="运行目录根路径（默认: workspace/article-to-video）",
    )
    parser.add_argument("--slug", default=None, help="可选自定义 slug")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    os.makedirs(root, exist_ok=True)

    run_dir = build_run_dir(root, args.title, args.slug)
    if os.path.exists(run_dir):
        print(f"ERROR: run directory already exists: {run_dir}", file=sys.stderr)
        raise SystemExit(1)

    dirs = ensure_dirs(run_dir)
    meta = {
        "title": args.title,
        "slug": os.path.basename(run_dir),
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "paths": dirs,
    }

    meta_path = os.path.join(run_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as file:
        json.dump(meta, file, ensure_ascii=False, indent=2)

    print(f"Run initialized: {run_dir}")
    print(f"Meta: {meta_path}")
    for name in ("slides", "preview", "audio", "build", "output", "canvas"):
        print(f"{name}: {dirs[name]}")


if __name__ == "__main__":
    main()
