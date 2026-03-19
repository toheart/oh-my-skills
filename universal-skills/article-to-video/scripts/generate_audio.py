"""
为每页讲稿生成 Edge-TTS 配音和 SRT 字幕。

用法:
    python generate_audio.py <outline.json> <output_dir> [--voice VOICE] [--rate RATE] [--pause SECONDS]

输出:
    <output_dir>/page_001.wav  — 每页配音（WAV 无损格式，含尾部静音间隔）
    <output_dir>/page_001.srt  — 每页字幕（word-level）
    <output_dir>/manifest.json — 每页音频时长清单

音频管线: Edge-TTS → MP3(原始) → WAV(后处理+追加静音) → render_video 一次性编码 AAC
使用 WAV 中间格式避免 MP3 多次编解码导致的电流声和时间偏移。
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys

try:
    import edge_tts
    from edge_tts import Communicate, SubMaker
except ImportError:
    print("ERROR: edge-tts not installed. Run: pip install edge-tts", file=sys.stderr)
    sys.exit(1)


async def generate_page_audio(text: str, output_wav: str, output_srt: str,
                               voice: str, rate: str, tail_pause: float) -> float:
    """为单页讲稿生成音频和字幕，返回最终音频时长（秒）。"""
    raw_mp3 = output_wav + ".raw.mp3"

    communicate = Communicate(text, voice, rate=rate)
    submaker = SubMaker()

    with open(raw_mp3, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)

    srt_content = submaker.get_srt()
    with open(output_srt, "w", encoding="utf-8") as srt_file:
        srt_file.write(srt_content)

    _postprocess_to_wav(raw_mp3, output_wav, tail_pause)
    if os.path.exists(raw_mp3):
        os.unlink(raw_mp3)

    duration = await get_audio_duration(output_wav)
    return duration


def _postprocess_to_wav(input_mp3: str, output_wav: str, tail_pause: float):
    """MP3 → WAV：一次解码 + 追加尾部静音。不做多余的编解码。"""
    try:
        if tail_pause > 0:
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-i", input_mp3,
                "-f", "lavfi", "-t", str(tail_pause),
                "-i", "anullsrc=r=24000:cl=mono",
                "-filter_complex",
                "[0:a]aformat=sample_rates=24000:channel_layouts=mono[voice];"
                "[1:a]aformat=sample_rates=24000:channel_layouts=mono[silence];"
                "[voice][silence]concat=n=2:v=0:a=1[out]",
                "-map", "[out]",
                "-c:a", "pcm_s16le",
                output_wav,
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-i", input_mp3,
                "-ar", "24000", "-ac", "1",
                "-c:a", "pcm_s16le",
                output_wav,
            ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"WARNING: WAV conversion failed, using raw mp3: {result.stderr}",
                  file=sys.stderr)
            os.replace(input_mp3, output_wav)
    except (FileNotFoundError, OSError):
        print("WARNING: ffmpeg not found, using raw mp3", file=sys.stderr)
        os.replace(input_mp3, output_wav)


async def get_audio_duration(filepath: str) -> float:
    """通过 ffprobe 获取音频时长（秒），不可用时按文件大小估算。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", filepath,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            info = json.loads(stdout)
            return float(info["format"]["duration"])
    except (FileNotFoundError, OSError):
        pass
    file_size = os.path.getsize(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".wav":
        return (file_size - 44) / (24000 * 2)  # 16bit mono 24kHz
    return file_size / 16000


async def main():
    parser = argparse.ArgumentParser(description="为每页讲稿生成 Edge-TTS 配音和字幕")
    parser.add_argument("outline", help="大纲 JSON 文件路径")
    parser.add_argument("output_dir", help="输出目录")
    parser.add_argument("--voice", default="zh-CN-YunjianNeural", help="TTS 语音（默认: zh-CN-YunjianNeural）")
    parser.add_argument("--rate", default="+0%", help="语速调节（默认: +0%%）")
    parser.add_argument("--pause", type=float, default=1.2, help="每页音频末尾追加的静音间隔/秒（默认: 1.2）")
    args = parser.parse_args()

    with open(args.outline, "r", encoding="utf-8") as f:
        outline = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    slides = outline.get("slides", [])
    if not slides:
        print("ERROR: outline.json has no slides", file=sys.stderr)
        sys.exit(1)

    manifest = {"title": outline.get("title", ""), "pages": []}

    for i, slide in enumerate(slides):
        page_num = i + 1
        script = slide.get("script", "")
        if not script.strip():
            print(f"WARNING: page {page_num} has empty script, skipping TTS", file=sys.stderr)
            manifest["pages"].append({
                "page": page_num,
                "heading": slide.get("heading", ""),
                "audio": None,
                "srt": None,
                "duration": 3.0,
            })
            continue

        wav_path = os.path.join(args.output_dir, f"page_{page_num:03d}.wav")
        srt_path = os.path.join(args.output_dir, f"page_{page_num:03d}.srt")

        print(f"Generating page {page_num}/{len(slides)}: {slide.get('heading', '')}")
        duration = await generate_page_audio(script, wav_path, srt_path, args.voice, args.rate, args.pause)

        manifest["pages"].append({
            "page": page_num,
            "heading": slide.get("heading", ""),
            "audio": os.path.basename(wav_path),
            "srt": os.path.basename(srt_path),
            "duration": round(duration, 2),
        })
        print(f"  -> {duration:.1f}s")

    manifest_path = os.path.join(args.output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    total_duration = sum(p["duration"] for p in manifest["pages"])
    print(f"\nDone. Total duration: {total_duration:.1f}s ({total_duration/60:.1f}min)")
    print(f"Manifest saved to: {manifest_path}")


if __name__ == "__main__":
    asyncio.run(main())
