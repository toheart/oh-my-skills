"""
将图片序列 + 音频 + 字幕合成为最终 MP4 视频。

用法:
    python render_video.py <manifest.json> <workspace_dir> [--output OUTPUT] [--transition SECONDS]

依赖: ffmpeg

工作原理:
    1. 为每页生成带音频的视频片段（图片 + 对应音频，时长由音频决定）
    2. 没有音频的页面生成静音片段（默认 3 秒）
    3. 烧录 SRT 字幕
    4. 默认保持静态画面，仅做轻微入退场淡化；如需镜头运动需显式开启
    5. 拼接所有片段，添加淡入淡出转场
"""

import argparse
import json
import math
import os
import shutil
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


def ensure_even(value: int) -> int:
    return value if value % 2 == 0 else value + 1


def parse_page_selector(value: str, total_pages: int) -> set[int]:
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
        raise ValueError(
            f"selected pages out of range: {invalid}; valid pages are 1-{total_pages}"
        )
    return pages


def resolve_target_pages(pages: list[dict], page_selector: str | None, chapter_id: str | None) -> set[int] | None:
    if page_selector and chapter_id:
        raise ValueError("--pages and --chapter cannot be used together")

    if page_selector:
        return parse_page_selector(page_selector, len(pages))

    if chapter_id:
        matched = {
            page["page"] for page in pages if page.get("chapter_id") == chapter_id
        }
        if not matched:
            raise ValueError(f"chapter_id '{chapter_id}' not found in manifest")
        return matched

    return None


def probe_duration(filepath: str) -> float | None:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", filepath],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def resolve_bgm_path(raw_path: str, workspace_dir: str, audio_dir: str) -> str:
    candidate_paths = [
        raw_path,
        os.path.join(workspace_dir, raw_path),
        os.path.join(audio_dir, raw_path),
    ]
    for candidate in candidate_paths:
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    print(f"ERROR: BGM file not found: {raw_path}", file=sys.stderr)
    sys.exit(1)


def resolve_bgm_config(manifest: dict, args: argparse.Namespace, workspace_dir: str, audio_dir: str) -> dict | None:
    config = manifest.get("bgm") if isinstance(manifest.get("bgm"), dict) else {}
    bgm_path = config.get("file")
    enabled = bool(config.get("enabled") and bgm_path)

    if args.bgm_file:
        bgm_path = args.bgm_file
        enabled = True

    if not enabled or not bgm_path:
        return None

    gain_db = args.bgm_gain_db if args.bgm_gain_db is not None else config.get("gain_db", -24.0)
    fade_in = args.bgm_fade_in if args.bgm_fade_in is not None else config.get("fade_in", 1.0)
    fade_out = args.bgm_fade_out if args.bgm_fade_out is not None else config.get("fade_out", 1.5)

    return {
        "file": resolve_bgm_path(str(bgm_path), workspace_dir, audio_dir),
        "gain_db": float(gain_db),
        "fade_in": float(fade_in),
        "fade_out": float(fade_out),
    }


def find_slide_image(workspace_dir: str, page_num: int) -> str:
    """查找对应页码的幻灯片图片，优先使用原生 PPT 导出的 images/。"""
    search_dirs = [
        workspace_dir,
        os.path.join(workspace_dir, "images"),
        os.path.join(workspace_dir, "native-preview"),
        os.path.join(workspace_dir, "preview"),
        os.path.join(workspace_dir, "build"),
    ]
    patterns = [
        f"slide-{page_num}.jpg",
        f"slide-{page_num:02d}.jpg",
        f"slide-{page_num:03d}.jpg",
        f"slide-{page_num}.png",
        f"slide-{page_num:02d}.png",
        f"slide-{page_num:03d}.png",
    ]
    for base_dir in search_dirs:
        for pattern in patterns:
            path = os.path.join(base_dir, pattern)
            if os.path.exists(path):
                return path
    print(f"ERROR: slide image not found for page {page_num} in {workspace_dir}", file=sys.stderr)
    sys.exit(1)


def select_motion_variant(motion: str, page_num: int) -> str:
    if motion != "auto":
        return motion
    sequence = ["drift-right", "drift-left", "drift-down", "drift-up"]
    return sequence[(page_num - 1) % len(sequence)]


def build_motion_filter(
    width: int,
    height: int,
    fps: int,
    duration: float,
    motion: str,
    motion_scale: float,
    fade_in: float,
    fade_out: float,
) -> str:
    if motion == "none":
        filter_chain = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps={fps}"
        )
    else:
        overscan_w = ensure_even(max(width + 2, int(math.ceil(width * (1.0 + motion_scale)))))
        overscan_h = ensure_even(max(height + 2, int(math.ceil(height * (1.0 + motion_scale)))))
        max_x = max(overscan_w - width, 0)
        max_y = max(overscan_h - height, 0)
        frames = max(int(math.ceil(duration * fps)), 1)
        frame_div = max(frames - 1, 1)
        x_center = f"{max_x}/2"
        y_center = f"{max_y}/2"

        x_expr = x_center
        y_expr = y_center
        if motion == "drift-right":
            x_expr = f"{max_x}*(0.12+0.76*n/{frame_div})"
        elif motion == "drift-left":
            x_expr = f"{max_x}*(0.88-0.76*n/{frame_div})"
        elif motion == "drift-down":
            y_expr = f"{max_y}*(0.12+0.76*n/{frame_div})"
        elif motion == "drift-up":
            y_expr = f"{max_y}*(0.88-0.76*n/{frame_div})"

        filter_chain = (
            f"[0:v]scale={overscan_w}:{overscan_h}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:x='{x_expr}':y='{y_expr}',"
            f"setsar=1,fps={fps}"
        )

    fade_in = max(0.0, fade_in)
    fade_out = max(0.0, fade_out)
    if fade_in > 0:
        filter_chain += f",fade=t=in:st=0:d={min(fade_in, duration):.2f}"
    if fade_out > 0 and duration > fade_out:
        filter_chain += f",fade=t=out:st={max(duration - fade_out, 0):.2f}:d={fade_out:.2f}"
    return filter_chain


def generate_page_clip(page: dict, workspace_dir: str, audio_dir: str,
                       clip_path: str, transition: float, width: int, height: int,
                       fps: int, subtitle_font_size: int, subtitle_margin_v: int,
                       motion: str, motion_scale: float, fade_in: float, fade_out: float):
    """为单页生成视频片段（图片 + 音频 + 字幕）。"""
    page_num = page["page"]
    duration = page["duration"]
    image_path = find_slide_image(workspace_dir, page_num)
    motion_variant = select_motion_variant(motion, page_num)

    if page["audio"]:
        audio_path = os.path.join(audio_dir, page["audio"])
        srt_path = os.path.join(audio_dir, page["srt"]) if page.get("srt") else None

        filter_chain = build_motion_filter(
            width,
            height,
            fps,
            duration,
            motion_variant,
            motion_scale,
            fade_in,
            fade_out,
        )

        # 烧录字幕
        if srt_path and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
            # ffmpeg 字幕路径需要转义反斜杠和冒号
            escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:").replace("'", r"\'")
            filter_chain += (
                f",subtitles=filename='{escaped_srt}'"
                f":force_style='FontName=Microsoft YaHei,FontSize={subtitle_font_size},"
                f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                f"BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV={subtitle_margin_v}'"
            )
        filter_complex = filter_chain + "[v]"

        run_ffmpeg([
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-t", str(duration),
            clip_path,
        ], desc=f"page {page_num}")
    else:
        # 没有音频，生成静音片段
        silent_filter = build_motion_filter(
            width,
            height,
            fps,
            duration,
            motion_variant,
            motion_scale,
            fade_in,
            fade_out,
        )
        run_ffmpeg([
            "-loop", "1", "-i", image_path,
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-filter_complex", silent_filter + "[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-t", str(duration),
            clip_path,
        ], desc=f"page {page_num} (silent)")


def concat_clips(clip_paths: list[str], output_path: str, transition: float):
    """拼接所有片段，添加淡入淡出转场。"""
    if not clip_paths:
        print("ERROR: no clips to concat", file=sys.stderr)
        sys.exit(1)

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    if len(clip_paths) == 1:
        shutil.copyfile(clip_paths[0], output_path)
        return

    # 使用 concat demuxer 拼接（简单可靠）
    # 先用 xfade 添加转场效果
    if transition > 0 and len(clip_paths) > 1:
        _concat_with_xfade(clip_paths, output_path, transition)
    else:
        _concat_simple(clip_paths, output_path)


def _concat_simple(clip_paths: list[str], output_path: str):
    """简单拼接，无转场。优先用 concat filter 避免中文路径编码问题。"""
    if len(clip_paths) <= 15:
        # concat filter 方式：通过 -i 传入，不经过文件列表，避免编码问题
        inputs = []
        for p in clip_paths:
            inputs.extend(["-i", p])
        n = len(clip_paths)
        streams = "".join(f"[{i}:v][{i}:a]" for i in range(n))
        filter_expr = f"{streams}concat=n={n}:v=1:a=1[vout][aout]"
        run_ffmpeg(
            inputs + [
                "-filter_complex", filter_expr,
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path,
            ],
            desc="concat-filter",
        )
    else:
        # 片段太多时回退到 concat demuxer
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
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
    # xfade 在片段多时 filter_complex 会很长，超过 15 个片段时回退到简单拼接
    if len(clip_paths) > 15:
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
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ],
        desc="xfade concat",
    )


def mix_global_bgm(input_video: str, output_path: str, bgm: dict):
    duration = probe_duration(input_video)
    if duration is None:
        print("ERROR: cannot determine video duration for BGM mix", file=sys.stderr)
        sys.exit(1)

    bgm_chain = f"[0:a]volume={bgm['gain_db']}dB,atrim=0:{duration:.2f}"
    if bgm["fade_in"] > 0:
        bgm_chain += f",afade=t=in:st=0:d={min(bgm['fade_in'], duration):.2f}"
    if bgm["fade_out"] > 0 and duration > bgm["fade_out"]:
        bgm_chain += f",afade=t=out:st={max(duration - bgm['fade_out'], 0):.2f}:d={bgm['fade_out']:.2f}"
    bgm_chain += "[bgm]"

    run_ffmpeg([
        "-stream_loop", "-1", "-i", bgm["file"],
        "-i", input_video,
        "-filter_complex", bgm_chain + ";[1:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]",
        "-map", "1:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        output_path,
    ], desc="global bgm mix")


def main():
    parser = argparse.ArgumentParser(description="合成 PPT 讲解视频")
    parser.add_argument("manifest", help="manifest.json 路径")
    parser.add_argument("workspace", help="工作目录（含 slide-*.jpg 图片）")
    parser.add_argument("--output", default=None, help="输出视频路径（默认: workspace/output/final.mp4）")
    parser.add_argument("--transition", type=float, default=0.0, help="转场时长/秒（默认: 0，不转场避免字幕重叠）")
    parser.add_argument("--width", type=int, default=1920, help="输出视频宽度（默认: 1920）")
    parser.add_argument("--height", type=int, default=1080, help="输出视频高度（默认: 1080）")
    parser.add_argument("--fps", type=int, default=30, help="输出帧率（默认: 30）")
    parser.add_argument("--subtitle-font-size", type=int, default=12, help="字幕字号（默认: 12）")
    parser.add_argument("--subtitle-margin-v", type=int, default=42, help="字幕底部边距（默认: 42）")
    parser.add_argument("--pages", default=None, help="仅重渲染指定页码，例如 3,5-7")
    parser.add_argument("--chapter", default=None, help="仅重渲染指定 chapter_id 下的页面")
    parser.add_argument("--bgm-file", default=None, help="为最终视频叠加全局 BGM 文件")
    parser.add_argument("--bgm-gain-db", type=float, default=None, help="全局 BGM 音量（dB，默认跟随 manifest 或 -24）")
    parser.add_argument("--bgm-fade-in", type=float, default=None, help="全局 BGM 淡入时长（秒）")
    parser.add_argument("--bgm-fade-out", type=float, default=None, help="全局 BGM 淡出时长（秒）")
    parser.add_argument(
        "--motion",
        choices=["auto", "none", "drift-right", "drift-left", "drift-down", "drift-up"],
        default="none",
        help="页面轻动态模式（默认: none，保持静态）",
    )
    parser.set_defaults(reuse_clips=True)
    parser.add_argument("--reuse-clips", dest="reuse_clips", action="store_true", help="局部重渲染时复用未改动的缓存片段（默认开启）")
    parser.add_argument("--no-reuse-clips", dest="reuse_clips", action="store_false", help="局部重渲染时不复用缓存片段")
    parser.add_argument("--motion-scale", type=float, default=0.06, help="轻动态放大比例（默认: 0.06）")
    parser.add_argument("--fade-in", type=float, default=0.28, help="每页入场淡化时长（默认: 0.28）")
    parser.add_argument("--fade-out", type=float, default=0.18, help="每页退场淡化时长（默认: 0.18）")
    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    audio_dir = os.path.dirname(os.path.abspath(args.manifest))
    workspace_dir = os.path.abspath(args.workspace)
    output_path = args.output or os.path.join(workspace_dir, "output", "final.mp4")

    pages = manifest.get("pages", [])
    if not pages:
        print("ERROR: manifest has no pages", file=sys.stderr)
        sys.exit(1)

    try:
        target_pages = resolve_target_pages(pages, args.pages, args.chapter)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if target_pages is None:
        print(f"Rendering all {len(pages)} pages")
    else:
        selected_text = ", ".join(str(page) for page in sorted(target_pages))
        print(f"Rendering selected pages and reusing cached clips where possible: {selected_text}")

    bgm = resolve_bgm_config(manifest, args, workspace_dir, audio_dir)
    if bgm:
        print(
            f"Applying global BGM from {bgm['file']} "
            f"(gain={bgm['gain_db']:.1f}dB, fade_in={bgm['fade_in']:.1f}s, fade_out={bgm['fade_out']:.1f}s)"
        )

    # 缓存目录存放中间片段，供局部重渲染复用
    clips_dir = os.path.join(workspace_dir, "build", "_clips")
    os.makedirs(clips_dir, exist_ok=True)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    clip_paths = []
    for page in pages:
        page_num = page["page"]
        clip_path = os.path.join(clips_dir, f"clip_{page_num:03d}.mp4")
        should_render = target_pages is None or page_num in target_pages or not (args.reuse_clips and os.path.exists(clip_path))
        if should_render:
            print(f"Rendering page {page_num}/{len(pages)}: {page.get('heading', '')}")
            generate_page_clip(
                page,
                workspace_dir,
                audio_dir,
                clip_path,
                args.transition,
                args.width,
                args.height,
                args.fps,
                args.subtitle_font_size,
                args.subtitle_margin_v,
                args.motion,
                args.motion_scale,
                args.fade_in,
                args.fade_out,
            )
        else:
            print(f"Reusing cached clip for page {page_num}/{len(pages)}: {page.get('heading', '')}")
        clip_paths.append(clip_path)

    print(f"\nConcatenating {len(clip_paths)} clips...")
    concat_output = output_path
    temp_concat_output = None
    if bgm:
        temp_concat_output = os.path.join(workspace_dir, "build", "_final_without_bgm.mp4")
        concat_output = temp_concat_output

    concat_clips(clip_paths, concat_output, args.transition)

    if bgm:
        mix_global_bgm(temp_concat_output, output_path, bgm)
        if os.path.exists(temp_concat_output):
            os.unlink(temp_concat_output)

    total_duration = sum(p["duration"] for p in pages)
    print(f"\nDone! Output: {output_path}")
    print(f"Duration: {total_duration:.1f}s ({total_duration/60:.1f}min)")
    print(f"Resolution: {args.width}x{args.height}, {args.fps}fps, H.264")


if __name__ == "__main__":
    main()
