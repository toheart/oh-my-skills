"""
为每页讲稿生成 Edge-TTS 配音和 SRT 字幕。

用法:
    python generate_audio.py <outline.json> <output_dir> [--voice VOICE|auto]

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
import re
import subprocess
import sys

try:
    import edge_tts
    from edge_tts import Communicate, SubMaker
except ImportError:
    print("ERROR: edge-tts not installed. Run: pip install edge-tts", file=sys.stderr)
    sys.exit(1)


DEFAULT_TTS_CONFIG = {
    "voice": "zh-CN-YunjianNeural",
    "rate": "+0%",
    "volume": "+0%",
    "pitch": "+0Hz",
    "pause": 1.2,
    "profile": "balanced",
    "reason": "fallback default profile",
}

AUTO_TTS_PROFILES = {
    "technical": {
        "voice": "zh-CN-YunjianNeural",
        "rate": "-5%",
        "volume": "+0%",
        "pitch": "+0Hz",
        "pause": 1.1,
        "reason": "technical and engineering language benefits from a steadier, slightly slower delivery",
    },
    "business": {
        "voice": "zh-CN-YunxiNeural",
        "rate": "-2%",
        "volume": "+0%",
        "pitch": "+0Hz",
        "pause": 1.0,
        "reason": "business and strategy content fits a composed, confident narration tone",
    },
    "story": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "rate": "-4%",
        "volume": "+2%",
        "pitch": "+0Hz",
        "pause": 1.3,
        "reason": "story-led or reflective material benefits from a warmer, slower voice",
    },
    "energetic": {
        "voice": "zh-CN-XiaoyiNeural",
        "rate": "+3%",
        "volume": "+2%",
        "pitch": "+2Hz",
        "pause": 0.9,
        "reason": "lighter lifestyle or youth-oriented content works better with a brighter pace",
    },
    "balanced": {
        "voice": "zh-CN-YunjianNeural",
        "rate": "-3%",
        "volume": "+0%",
        "pitch": "+0Hz",
        "pause": 1.1,
        "reason": "mixed-topic explainers need a stable, general-purpose narration profile",
    },
}

PROFILE_KEYWORDS = {
    "technical": {
        "ai", "agent", "api", "architecture", "backend", "code", "coding", "ddd",
        "engineering", "frontend", "git", "golang", "llm", "mcp", "model", "openai",
        "prompt", "python", "react", "repo", "skill", "sdd", "system", "tdd",
        "workflow", "产品技术", "代码", "前端", "后端", "工程", "开发", "技术", "接口",
        "架构", "模型", "测试", "流程", "算法", "系统", "评测", "部署",
    },
    "business": {
        "business", "case", "ceo", "company", "growth", "kpi", "market", "okr",
        "operation", "revenue", "roadmap", "sales", "strategy", "商业", "增长",
        "复盘", "战略", "市场", "汇报", "管理", "组织", "运营",
    },
    "story": {
        "essay", "history", "journey", "memory", "poem", "reflection", "story",
        "travel", "人物", "传记", "历史", "叙事", "回忆", "故事", "旅行", "文化", "随笔",
    },
    "energetic": {
        "daily", "fun", "game", "lifestyle", "music", "trend", "vlog", "年轻",
        "娱乐", "好玩", "潮流", "生活", "短视频", "轻松", "青年",
    },
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def score_profile(text: str, keywords: set[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def pick_auto_profile(outline: dict) -> dict:
    tts_from_outline = outline.get("tts")
    if isinstance(tts_from_outline, dict) and tts_from_outline.get("profile") in AUTO_TTS_PROFILES:
        profile_name = tts_from_outline["profile"]
        profile = dict(AUTO_TTS_PROFILES[profile_name])
        profile["profile"] = profile_name
        profile["reason"] = (
            f"outline.json requested tts.profile='{profile_name}', so the auto preset follows that hint"
        )
        return profile

    text_fragments = [outline.get("title", "")]
    for slide in outline.get("slides", []):
        text_fragments.extend([
            slide.get("heading", ""),
            " ".join(slide.get("bullets", [])),
            slide.get("script", ""),
        ])
    corpus = normalize_text(" ".join(text_fragments))

    scores = {
        profile_name: score_profile(corpus, keywords)
        for profile_name, keywords in PROFILE_KEYWORDS.items()
    }

    ordered_candidates = sorted(
        scores.items(),
        key=lambda item: (item[1], item[0] == "technical", item[0] == "balanced"),
        reverse=True,
    )
    top_profile, top_score = ordered_candidates[0]

    if top_score <= 0:
        top_profile = "balanced"

    profile = dict(AUTO_TTS_PROFILES[top_profile])
    profile["profile"] = top_profile

    if top_score <= 0:
        profile["reason"] = "no strong topic signal detected, so a balanced narration preset was selected"
    else:
        profile["reason"] = (
            f"matched profile '{top_profile}' from article keywords, title, bullets, and slide scripts"
        )

    return profile


def coerce_pause(value, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def merge_tts_config(base: dict, override) -> dict:
    config = dict(base)
    if not isinstance(override, dict):
        return config
    for key in ("voice", "rate", "volume", "pitch", "profile", "reason"):
        if override.get(key):
            config[key] = override[key]
    if "pause" in override:
        config["pause"] = coerce_pause(override.get("pause"), config["pause"])
    return config


def resolve_tts_config(outline: dict, args: argparse.Namespace) -> dict:
    outline_tts = outline.get("tts") if isinstance(outline.get("tts"), dict) else {}
    auto_profile = pick_auto_profile(outline)

    if args.voice == "auto":
        resolved = merge_tts_config(DEFAULT_TTS_CONFIG, auto_profile)
        resolved = merge_tts_config(resolved, outline_tts)
        resolved["source"] = "auto"
    else:
        resolved = merge_tts_config(DEFAULT_TTS_CONFIG, outline_tts)
        resolved["voice"] = args.voice
        resolved["profile"] = "manual"
        resolved["reason"] = "voice was explicitly provided on the command line"
        resolved["source"] = "manual"

    if args.rate is not None:
        resolved["rate"] = args.rate
    if args.volume is not None:
        resolved["volume"] = args.volume
    if args.pitch is not None:
        resolved["pitch"] = args.pitch
    if args.pause is not None:
        resolved["pause"] = args.pause
    else:
        resolved["pause"] = coerce_pause(resolved.get("pause"), DEFAULT_TTS_CONFIG["pause"])

    return resolved


async def generate_page_audio(
    text: str,
    output_wav: str,
    output_srt: str,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
    tail_pause: float,
) -> float:
    """为单页讲稿生成音频和字幕，返回最终音频时长（秒）。"""
    raw_mp3 = output_wav + ".raw.mp3"

    communicate = Communicate(text, voice, rate=rate, volume=volume, pitch=pitch)
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
    parser.add_argument("--voice", default="auto", help="TTS 语音，支持具体 voice id 或 auto（默认: auto）")
    parser.add_argument("--rate", default=None, help="语速调节；未提供时跟随 auto profile 或 outline.json 中的 tts 配置")
    parser.add_argument("--volume", default=None, help="音量调节；未提供时跟随 auto profile 或 outline.json 中的 tts 配置")
    parser.add_argument("--pitch", default=None, help="音高调节；未提供时跟随 auto profile 或 outline.json 中的 tts 配置")
    parser.add_argument("--pause", type=float, default=None, help="每页音频末尾追加的静音间隔/秒；未提供时跟随配置")
    args = parser.parse_args()

    with open(args.outline, "r", encoding="utf-8") as f:
        outline = json.load(f)

    os.makedirs(args.output_dir, exist_ok=True)

    slides = outline.get("slides", [])
    if not slides:
        print("ERROR: outline.json has no slides", file=sys.stderr)
        sys.exit(1)

    base_tts_config = resolve_tts_config(outline, args)
    print("Resolved TTS profile:")
    print(
        "  "
        f"profile={base_tts_config['profile']} voice={base_tts_config['voice']} "
        f"rate={base_tts_config['rate']} volume={base_tts_config['volume']} "
        f"pitch={base_tts_config['pitch']} pause={base_tts_config['pause']:.2f}s"
    )
    print(f"  reason={base_tts_config['reason']}")

    manifest = {
        "title": outline.get("title", ""),
        "tts": {
            "profile": base_tts_config["profile"],
            "voice": base_tts_config["voice"],
            "rate": base_tts_config["rate"],
            "volume": base_tts_config["volume"],
            "pitch": base_tts_config["pitch"],
            "pause": round(base_tts_config["pause"], 2),
            "source": base_tts_config["source"],
            "reason": base_tts_config["reason"],
        },
        "pages": [],
    }

    for i, slide in enumerate(slides):
        page_num = i + 1
        script = slide.get("script", "")
        page_tts_config = merge_tts_config(base_tts_config, slide.get("tts"))
        if not script.strip():
            print(f"WARNING: page {page_num} has empty script, skipping TTS", file=sys.stderr)
            manifest["pages"].append({
                "page": page_num,
                "heading": slide.get("heading", ""),
                "audio": None,
                "srt": None,
                "duration": 3.0,
                "tts": {
                    "voice": page_tts_config["voice"],
                    "rate": page_tts_config["rate"],
                    "volume": page_tts_config["volume"],
                    "pitch": page_tts_config["pitch"],
                    "pause": round(page_tts_config["pause"], 2),
                },
            })
            continue

        wav_path = os.path.join(args.output_dir, f"page_{page_num:03d}.wav")
        srt_path = os.path.join(args.output_dir, f"page_{page_num:03d}.srt")

        print(
            f"Generating page {page_num}/{len(slides)}: {slide.get('heading', '')} "
            f"[{page_tts_config['voice']}, {page_tts_config['rate']}]"
        )
        duration = await generate_page_audio(
            script,
            wav_path,
            srt_path,
            page_tts_config["voice"],
            page_tts_config["rate"],
            page_tts_config["volume"],
            page_tts_config["pitch"],
            page_tts_config["pause"],
        )

        manifest["pages"].append({
            "page": page_num,
            "heading": slide.get("heading", ""),
            "audio": os.path.basename(wav_path),
            "srt": os.path.basename(srt_path),
            "duration": round(duration, 2),
            "tts": {
                "voice": page_tts_config["voice"],
                "rate": page_tts_config["rate"],
                "volume": page_tts_config["volume"],
                "pitch": page_tts_config["pitch"],
                "pause": round(page_tts_config["pause"], 2),
            },
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
