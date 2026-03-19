"""
将图片序列 + 音频 + 字幕合成为最终 MP4 视频。

用法:
    python render_video.py <manifest.json> <workspace_dir> [--output OUTPUT] [--transition SECONDS]

依赖: ffmpeg

工作原理:
    1. 为每页生成带音频的视频片段（图片 + 对应音频，时长由音频决定）
    2. 没有音频的页面生成静音片段（默认 3 秒）
    3. 烧录 SRT 字幕
    4. 拼接所有片段，添加淡入淡出转场
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile


def run_ffmpeg(args: list[str], desc: str = ""):
    """执行 ffmpeg 命令，失败时报错退出。"""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR ({desc}): {result.stderr}", file=sys.stderr)
        sys.exit(1)


def find_slide_image(workspace_dir: str, page_num: int) -> str:
    """查找对应页码的幻灯片图片（pdftoppm 输出格式）。"""
    # pdftoppm 输出格式: slide-1.jpg, slide-01.jpg, slide-001.jpg
    for pattern in [f"slide-{page_num}.jpg", f"slide-{page_num:02d}.jpg", f"slide-{page_num:03d}.jpg"]:
        path = os.path.join(workspace_dir, pattern)
        if os.path.exists(path):
            return path
    # 也支持 png 格式
    for pattern in [f"slide-{page_num}.png", f"slide-{page_num:02d}.png", f"slide-{page_num:03d}.png"]:
        path = os.path.join(workspace_dir, pattern)
        if os.path.exists(path):
            return path
    print(f"ERROR: slide image not found for page {page_num} in {workspace_dir}", file=sys.stderr)
    sys.exit(1)


def generate_page_clip(page: dict, workspace_dir: str, audio_dir: str,
                       clip_path: str, transition: float):
    """为单页生成视频片段（图片 + 音频 + 字幕）。"""
    page_num = page["page"]
    duration = page["duration"]
    image_path = find_slide_image(workspace_dir, page_num)

    if page["audio"]:
        audio_path = os.path.join(audio_dir, page["audio"])
        srt_path = os.path.join(audio_dir, page["srt"]) if page.get("srt") else None

        # 图片 + 音频 → 视频片段
        filter_parts = [
            f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps=30"
        ]

        # 烧录字幕
        if srt_path and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
            # ffmpeg 字幕路径需要转义反斜杠和冒号
            escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
            filter_parts[0] += (
                f",subtitles='{escaped_srt}'"
                f":force_style='FontName=Microsoft YaHei,FontSize=12,"
                f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                f"BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=25'"
            )

        filter_complex = filter_parts[0] + "[v]"

        run_ffmpeg([
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            clip_path,
        ], desc=f"page {page_num}")
    else:
        # 没有音频，生成静音片段
        run_ffmpeg([
            "-loop", "1", "-i", image_path,
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-vf", f"scale=1920:1080:force_original_aspect_ratio=decrease,"
                   f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            clip_path,
        ], desc=f"page {page_num} (silent)")


def concat_clips(clip_paths: list[str], output_path: str, transition: float):
    """拼接所有片段，添加淡入淡出转场。"""
    if not clip_paths:
        print("ERROR: no clips to concat", file=sys.stderr)
        sys.exit(1)

    if len(clip_paths) == 1:
        os.rename(clip_paths[0], output_path)
        return

    # 使用 concat demuxer 拼接（简单可靠）
    # 先用 xfade 添加转场效果
    if transition > 0 and len(clip_paths) > 1:
        _concat_with_xfade(clip_paths, output_path, transition)
    else:
        _concat_simple(clip_paths, output_path)


def _concat_simple(clip_paths: list[str], output_path: str):
    """简单拼接，无转场。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
        list_file = f.name

    try:
        run_ffmpeg([
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy", output_path,
        ], desc="concat")
    finally:
        os.unlink(list_file)


def _concat_with_xfade(clip_paths: list[str], output_path: str, transition: float):
    """带 xfade 淡入淡出转场的拼接。"""
    # xfade 在片段多时 filter_complex 会很长，超过 10 个片段时回退到简单拼接
    if len(clip_paths) > 10:
        print("WARNING: too many clips for xfade, falling back to simple concat", file=sys.stderr)
        _concat_simple(clip_paths, output_path)
        return

    inputs = []
    for p in clip_paths:
        inputs.extend(["-i", p])

    # 获取每个片段的时长
    durations = []
    for p in clip_paths:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", p],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            durations.append(float(info["format"]["duration"]))
        else:
            durations.append(5.0)

    # 构建 xfade filter chain
    # 视频: [0][1]xfade -> [v01], [v01][2]xfade -> [v012], ...
    # 音频: [0][1]acrossfade -> [a01], [a01][2]acrossfade -> [a012], ...
    n = len(clip_paths)
    video_filters = []
    audio_filters = []
    offset = durations[0] - transition

    for i in range(1, n):
        if i == 1:
            v_in = f"[0:v][1:v]"
        else:
            v_in = f"[v{i-1}][{i}:v]"
        v_out = f"[v{i}]" if i < n - 1 else "[vout]"
        video_filters.append(f"{v_in}xfade=transition=fade:duration={transition}:offset={offset:.2f}{v_out}")

        if i == 1:
            a_in = f"[0:a][1:a]"
        else:
            a_in = f"[a{i-1}][{i}:a]"
        a_out = f"[a{i}]" if i < n - 1 else "[aout]"
        audio_filters.append(f"{a_in}acrossfade=d={transition}:c1=tri:c2=tri{a_out}")

        if i < n - 1:
            offset += durations[i] - transition

    filter_complex = ";".join(video_filters + audio_filters)

    run_ffmpeg(
        inputs + [
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            output_path,
        ],
        desc="xfade concat",
    )


def main():
    parser = argparse.ArgumentParser(description="合成 PPT 讲解视频")
    parser.add_argument("manifest", help="manifest.json 路径")
    parser.add_argument("workspace", help="工作目录（含 slide-*.jpg 图片）")
    parser.add_argument("--output", default=None, help="输出视频路径（默认: workspace/output.mp4）")
    parser.add_argument("--transition", type=float, default=0.0, help="转场时长/秒（默认: 0，不转场避免字幕重叠）")
    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    audio_dir = os.path.dirname(os.path.abspath(args.manifest))
    workspace_dir = os.path.abspath(args.workspace)
    output_path = args.output or os.path.join(workspace_dir, "output.mp4")

    pages = manifest.get("pages", [])
    if not pages:
        print("ERROR: manifest has no pages", file=sys.stderr)
        sys.exit(1)

    # 临时目录存放中间片段
    clips_dir = os.path.join(workspace_dir, "_clips")
    os.makedirs(clips_dir, exist_ok=True)

    clip_paths = []
    for page in pages:
        page_num = page["page"]
        clip_path = os.path.join(clips_dir, f"clip_{page_num:03d}.mp4")
        print(f"Rendering page {page_num}/{len(pages)}: {page.get('heading', '')}")
        generate_page_clip(page, workspace_dir, audio_dir, clip_path, args.transition)
        clip_paths.append(clip_path)

    print(f"\nConcatenating {len(clip_paths)} clips...")
    concat_clips(clip_paths, output_path, args.transition)

    # 清理临时片段
    for p in clip_paths:
        if os.path.exists(p):
            os.unlink(p)
    if os.path.exists(clips_dir):
        try:
            os.rmdir(clips_dir)
        except OSError:
            pass

    total_duration = sum(p["duration"] for p in pages)
    print(f"\nDone! Output: {output_path}")
    print(f"Duration: {total_duration:.1f}s ({total_duration/60:.1f}min)")
    print(f"Resolution: 1920x1080, 30fps, H.264")


if __name__ == "__main__":
    main()
