"""
视频质量自检脚本：检测音画同步、电流/卡顿、字幕同步等问题。

用法:
    python verify_video.py <output.mp4> <manifest.json>

检测项:
    1. 音画同步：视频轨时长 vs 音频轨时长，偏差超过 0.5s 报警
    2. 音频质量：检测异常峰值/静音段（可能是电流声或编码损坏）
    3. 字幕同步：SRT 最后时间戳 vs 对应音频实际时长，偏差超过 1s 报警
    4. 片段时长一致性：manifest 记录的 duration vs 实际音频 duration
    5. 基本规格校验：分辨率、帧率、编码格式
"""

import argparse
import json
import os
import re
import subprocess
import sys


def run_ffprobe(args: list[str]) -> dict | None:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    return None


def parse_srt_end_time(srt_path: str) -> float | None:
    """解析 SRT 文件中最后一条字幕的结束时间（秒）。"""
    if not os.path.exists(srt_path) or os.path.getsize(srt_path) == 0:
        return None
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()
    timestamps = re.findall(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", content)
    if not timestamps:
        return None
    last = timestamps[-1]
    return int(last[0]) * 3600 + int(last[1]) * 60 + int(last[2]) + int(last[3]) / 1000


def check_video_specs(video_path: str) -> list[str]:
    """检查视频基本规格。"""
    issues = []
    info = run_ffprobe(["-show_streams", "-show_format", video_path])
    if not info:
        issues.append("FATAL: cannot read video file with ffprobe")
        return issues

    video_stream = None
    audio_stream = None
    for s in info.get("streams", []):
        if s["codec_type"] == "video" and not video_stream:
            video_stream = s
        elif s["codec_type"] == "audio" and not audio_stream:
            audio_stream = s

    if not video_stream:
        issues.append("FATAL: no video stream found")
        return issues
    if not audio_stream:
        issues.append("FATAL: no audio stream found")
        return issues

    w = int(video_stream.get("width", 0))
    h = int(video_stream.get("height", 0))
    if w != 1920 or h != 1080:
        issues.append(f"WARN: resolution {w}x{h}, expected 1920x1080")

    codec = video_stream.get("codec_name", "")
    if codec != "h264":
        issues.append(f"WARN: video codec '{codec}', expected h264")

    fps_str = video_stream.get("r_frame_rate", "")
    if fps_str:
        parts = fps_str.split("/")
        if len(parts) == 2 and int(parts[1]) > 0:
            fps = int(parts[0]) / int(parts[1])
            if abs(fps - 30) > 1:
                issues.append(f"WARN: framerate {fps:.1f}fps, expected ~30fps")

    a_codec = audio_stream.get("codec_name", "")
    if a_codec != "aac":
        issues.append(f"WARN: audio codec '{a_codec}', expected aac")

    a_bitrate = int(audio_stream.get("bit_rate", 0))
    if a_bitrate < 10000:
        issues.append(f"ERROR: audio bitrate {a_bitrate}bps, too low (likely silent)")

    return issues


def check_av_sync(video_path: str) -> list[str]:
    """检查音画同步：视频轨 vs 音频轨时长偏差。"""
    issues = []
    info = run_ffprobe(["-show_streams", video_path])
    if not info:
        return ["ERROR: cannot read streams"]

    v_dur = None
    a_dur = None
    for s in info.get("streams", []):
        dur = float(s.get("duration", 0))
        if s["codec_type"] == "video":
            v_dur = dur
        elif s["codec_type"] == "audio":
            a_dur = dur

    if v_dur is not None and a_dur is not None:
        diff = abs(v_dur - a_dur)
        if diff > 0.5:
            issues.append(
                f"ERROR: A/V duration mismatch: video={v_dur:.2f}s audio={a_dur:.2f}s "
                f"(diff={diff:.2f}s, threshold=0.5s)"
            )
        elif diff > 0.1:
            issues.append(
                f"WARN: minor A/V drift: video={v_dur:.2f}s audio={a_dur:.2f}s "
                f"(diff={diff:.2f}s)"
            )
    return issues


def check_audio_quality(video_path: str) -> list[str]:
    """检测音频质量：异常静音段、整体音量过低。"""
    issues = []
    cmd = [
        "ffmpeg", "-hide_banner", "-i", video_path,
        "-af", "silencedetect=noise=-40dB:d=3",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr

    silences = re.findall(r"silence_duration: ([\d.]+)", stderr)
    for dur_str in silences:
        dur = float(dur_str)
        if dur > 5:
            issues.append(f"WARN: long silence detected ({dur:.1f}s), may indicate audio issue")

    vol_cmd = [
        "ffmpeg", "-hide_banner", "-i", video_path,
        "-af", "volumedetect", "-f", "null", "-"
    ]
    vol_result = subprocess.run(vol_cmd, capture_output=True, text=True)
    vol_match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", vol_result.stderr)
    if vol_match:
        mean_vol = float(vol_match.group(1))
        if mean_vol < -40:
            issues.append(f"ERROR: mean volume {mean_vol:.1f}dB, audio is nearly silent")
        elif mean_vol < -30:
            issues.append(f"WARN: mean volume {mean_vol:.1f}dB, audio is quite low")

    max_match = re.search(r"max_volume:\s*([-\d.]+)\s*dB", vol_result.stderr)
    if max_match:
        max_vol = float(max_match.group(1))
        if max_vol > -0.5:
            issues.append(f"WARN: max volume {max_vol:.1f}dB, audio may be clipping")

    return issues


def check_subtitle_sync(manifest: dict, audio_dir: str) -> list[str]:
    """检查每页字幕结束时间 vs 音频时长的偏差。"""
    issues = []
    for page in manifest.get("pages", []):
        if not page.get("srt"):
            continue

        srt_path = os.path.join(audio_dir, page["srt"])
        srt_end = parse_srt_end_time(srt_path)
        if srt_end is None:
            issues.append(f"WARN: page {page['page']}: SRT is empty or unreadable")
            continue

        audio_path = os.path.join(audio_dir, page["audio"])
        info = run_ffprobe(["-show_format", audio_path])
        if info:
            actual_dur = float(info["format"]["duration"])
        else:
            actual_dur = page["duration"]

        # 字幕应在音频结束前结束（音频含尾部静音），但不应差太多
        # SRT 结束时间 应 < 音频时长（因为有尾部静音）
        # 如果 SRT 结束时间 > 音频时长，说明字幕超出了音频
        if srt_end > actual_dur + 0.5:
            issues.append(
                f"ERROR: page {page['page']}: subtitle ends at {srt_end:.1f}s "
                f"but audio is {actual_dur:.1f}s (subtitle overflows)"
            )

        manifest_dur = page["duration"]
        dur_diff = abs(manifest_dur - actual_dur)
        if dur_diff > 0.5:
            issues.append(
                f"WARN: page {page['page']}: manifest duration {manifest_dur:.2f}s "
                f"vs actual {actual_dur:.2f}s (diff={dur_diff:.2f}s)"
            )

    return issues


def main():
    parser = argparse.ArgumentParser(description="视频质量自检")
    parser.add_argument("video", help="视频文件路径")
    parser.add_argument("manifest", help="manifest.json 路径")
    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    audio_dir = os.path.dirname(os.path.abspath(args.manifest))

    all_issues = []
    checks = [
        ("Video Specs", lambda: check_video_specs(args.video)),
        ("A/V Sync", lambda: check_av_sync(args.video)),
        ("Audio Quality", lambda: check_audio_quality(args.video)),
        ("Subtitle Sync", lambda: check_subtitle_sync(manifest, audio_dir)),
    ]

    for name, check_fn in checks:
        print(f"\n{'='*50}")
        print(f"  {name}")
        print(f"{'='*50}")
        issues = check_fn()
        if issues:
            for issue in issues:
                level = issue.split(":")[0]
                marker = {"ERROR": "[X]", "WARN": "[!]", "FATAL": "[XX]"}.get(level, "[?]")
                print(f"  {marker} {issue}")
            all_issues.extend(issues)
        else:
            print(f"  [OK] All checks passed")

    print(f"\n{'='*50}")
    errors = [i for i in all_issues if i.startswith(("ERROR", "FATAL"))]
    warns = [i for i in all_issues if i.startswith("WARN")]
    print(f"  Summary: {len(errors)} errors, {len(warns)} warnings")
    if errors:
        print(f"  [FAIL] Video has quality issues that need fixing")
        sys.exit(1)
    elif warns:
        print(f"  [WARN] Video has minor issues, review recommended")
        sys.exit(0)
    else:
        print(f"  [PASS] Video passed all quality checks")
        sys.exit(0)


if __name__ == "__main__":
    main()
