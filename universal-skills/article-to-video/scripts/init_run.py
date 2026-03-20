"""
初始化 article-to-video 的独立运行目录。

用法:
    python init_run.py "文章标题"
    python init_run.py "文章标题" --root workspace/article-to-video
    python init_run.py "文章标题" --slug my-custom-slug

输出:
    <run_dir>/brief.json
    <run_dir>/meta.json
    <run_dir>/deck/
    <run_dir>/images/
    <run_dir>/audio/
    <run_dir>/build/
    <run_dir>/output/
    <run_dir>/canvas/
    <run_dir>/assets/bgm/
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
        "deck": os.path.join(run_dir, "deck"),
        "images": os.path.join(run_dir, "images"),
        "audio": os.path.join(run_dir, "audio"),
        "build": os.path.join(run_dir, "build"),
        "output": os.path.join(run_dir, "output"),
        "canvas": os.path.join(run_dir, "canvas"),
        "assets": os.path.join(run_dir, "assets"),
        "assets_bgm": os.path.join(run_dir, "assets", "bgm"),
    }
    for path in dirs.values():
        os.makedirs(path, exist_ok=True)
    return dirs


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


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
    write_json(meta_path, meta)

    brief_path = os.path.join(run_dir, "brief.json")
    outline_path = os.path.join(run_dir, "outline.json")
    slide_spec_path = os.path.join(run_dir, "slide-spec.json")

    write_json(
        brief_path,
        {
            "title": args.title,
            "article_understanding": {
                "core_message": "",
                "audience": "",
                "tone": "",
                "video_type": "",
            },
            "production_plan": {
                "recommended_duration": "",
                "chapter_count": 0,
                "visual_direction": "",
                "tts_profile": "",
                "bgm_strategy": "",
            },
        },
    )
    write_json(
        outline_path,
        {
            "title": args.title,
            "theme": {},
            "tts": {},
            "bgm": {},
            "slides": [],
        },
    )
    write_json(
        slide_spec_path,
        {
            "schema_version": "1.0",
            "kind": "slide-spec",
            "title": args.title,
            "theme": {},
            "tts": {},
            "bgm": {},
            "render": {
                "width": 1920,
                "height": 1080,
                "footer_safe_height": 156,
            },
            "pages": [],
        },
    )

    print(f"Run initialized: {run_dir}")
    print(f"Meta: {meta_path}")
    print(f"Brief: {brief_path}")
    print(f"Outline: {outline_path}")
    print(f"SlideSpec: {slide_spec_path}")
    for name in ("deck", "images", "audio", "build", "output", "canvas", "assets", "assets_bgm"):
        print(f"{name}: {dirs[name]}")


if __name__ == "__main__":
    main()
