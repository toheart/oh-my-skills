#!/usr/bin/env python3
"""
Generate voiceover audio and subtitles for a normalized remotion-video storyboard.

This script is adapted from the article-to-video audio pipeline but copied into
remotion-video so the skill does not depend on another skill at runtime.

Usage:
    python generate_audio.py <storyboard.json> <output_dir> [--voice VOICE|auto]

Output:
    <output_dir>/scene_001.wav        - per-scene WAV files
    <output_dir>/scene_001.srt        - per-scene subtitle files
    <output_dir>/voiceover.wav        - merged voiceover track
    <output_dir>/subtitles.srt        - merged subtitle file
    <output_dir>/captions.json        - merged caption entries for inline rendering
    <output_dir>/manifest.json        - timing and TTS manifest

If --update-storyboard is passed, the script rewrites the normalized storyboard
with actual scene timing, voiceover path, subtitle path, and inline captions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import sys
import wave
from typing import Any

try:
    from edge_tts import Communicate, SubMaker
except ImportError:
    print("ERROR: edge-tts not installed. Run: pip install edge-tts", file=sys.stderr)
    sys.exit(1)


DEFAULT_TTS_CONFIG = {
    "voice": "zh-CN-YunjianNeural",
    "rate": "+0%",
    "volume": "+0%",
    "pitch": "+0Hz",
    "pause": 0.4,
    "profile": "balanced",
    "reason": "fallback default profile",
}

AUTO_TTS_PROFILES = {
    "technical": {
        "voice": "zh-CN-YunjianNeural",
        "rate": "-5%",
        "volume": "+0%",
        "pitch": "+0Hz",
        "pause": 0.35,
        "reason": "technical and engineering language benefits from a steadier, slightly slower delivery",
    },
    "business": {
        "voice": "zh-CN-YunxiNeural",
        "rate": "-2%",
        "volume": "+0%",
        "pitch": "+0Hz",
        "pause": 0.35,
        "reason": "business and strategy content fits a composed, confident narration tone",
    },
    "story": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "rate": "-4%",
        "volume": "+2%",
        "pitch": "+0Hz",
        "pause": 0.5,
        "reason": "story-led or reflective material benefits from a warmer, slower voice",
    },
    "energetic": {
        "voice": "zh-CN-XiaoyiNeural",
        "rate": "+3%",
        "volume": "+2%",
        "pitch": "+2Hz",
        "pause": 0.25,
        "reason": "lighter lifestyle or youth-oriented content works better with a brighter pace",
    },
    "balanced": {
        "voice": "zh-CN-YunjianNeural",
        "rate": "-3%",
        "volume": "+0%",
        "pitch": "+0Hz",
        "pause": 0.4,
        "reason": "mixed-topic explainers need a stable, general-purpose narration profile",
    },
}

PROFILE_KEYWORDS = {
    "technical": {
        "ai", "agent", "api", "architecture", "backend", "code", "coding", "engineering",
        "frontend", "git", "llm", "model", "openai", "prompt", "python", "react",
        "repo", "system", "workflow", "代码", "前端", "后端", "工程", "技术", "模型",
        "测试", "流程", "算法", "系统", "部署",
    },
    "business": {
        "business", "case", "company", "growth", "kpi", "market", "okr", "operation",
        "revenue", "roadmap", "sales", "strategy", "商业", "增长", "战略", "市场",
        "汇报", "管理", "组织", "运营",
    },
    "story": {
        "essay", "history", "journey", "memory", "reflection", "story", "travel",
        "人物", "传记", "历史", "叙事", "回忆", "故事", "旅行", "文化", "随笔",
    },
    "energetic": {
        "daily", "fun", "game", "lifestyle", "music", "trend", "vlog", "娱乐",
        "好玩", "潮流", "生活", "短视频", "轻松",
    },
}


FFMPEG_BINARY = os.environ.get("FFMPEG_BINARY", "ffmpeg")
FFPROBE_BINARY = os.environ.get("FFPROBE_BINARY", "ffprobe")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def score_profile(text: str, keywords: set[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, value: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def score_storyboard_profile(storyboard: dict[str, Any]) -> dict[str, Any]:
    source = storyboard.get("source", {}) if isinstance(storyboard.get("source"), dict) else {}
    text_fragments = [
        storyboard.get("meta", {}).get("title", ""),
        source.get("core_thesis", ""),
        source.get("audience", ""),
        source.get("tone", ""),
    ]
    for scene in storyboard.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        text_fragments.extend(
            [
                scene.get("purpose", ""),
                scene.get("narration", ""),
                " ".join(ensure_list(scene.get("on_screen_text"))),
                scene.get("visual_prompt", ""),
            ]
        )

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
    runner_up_score = ordered_candidates[1][1] if len(ordered_candidates) > 1 else 0

    # 当首位和次位得分差距不足 2 时，认为信号不够明确，回退到 balanced
    if top_score <= 0 or (top_score > 0 and top_score - runner_up_score < 2):
        top_profile = "balanced"

    profile = dict(AUTO_TTS_PROFILES[top_profile])
    profile["profile"] = top_profile
    if top_score <= 0:
        profile["reason"] = "no strong topic signal detected, so a balanced narration preset was selected"
    elif top_score - runner_up_score < 2:
        runner_up_profile = ordered_candidates[1][0] if len(ordered_candidates) > 1 else "none"
        profile["reason"] = (
            f"top profiles '{ordered_candidates[0][0]}' ({top_score}) and "
            f"'{runner_up_profile}' ({runner_up_score}) are too close, "
            f"falling back to balanced for stability"
        )
    else:
        profile["reason"] = f"matched profile '{top_profile}' from storyboard title, source, scenes, and narration"
    return profile


def coerce_pause(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def merge_tts_config(base: dict[str, Any], override: Any) -> dict[str, Any]:
    config = dict(base)
    if not isinstance(override, dict):
        return config
    for key in ("voice", "rate", "volume", "pitch", "profile", "reason"):
        if override.get(key):
            config[key] = override[key]
    if "pause" in override:
        config["pause"] = coerce_pause(override.get("pause"), config["pause"])
    return config


def resolve_tts_config(storyboard: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    source = storyboard.get("source", {}) if isinstance(storyboard.get("source"), dict) else {}
    outline_tts = source.get("tts") if isinstance(source.get("tts"), dict) else {}
    auto_profile = score_storyboard_profile(storyboard)

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


def _run_subprocess(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _postprocess_to_wav(input_mp3: str, output_wav: str, tail_pause: float):
    try:
        if tail_pause > 0:
            cmd = [
                FFMPEG_BINARY,
                "-y",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-i",
                input_mp3,
                "-f",
                "lavfi",
                "-t",
                str(tail_pause),
                "-i",
                "anullsrc=r=24000:cl=mono",
                "-filter_complex",
                "[0:a]aformat=sample_rates=24000:channel_layouts=mono[voice];"
                "[1:a]aformat=sample_rates=24000:channel_layouts=mono[silence];"
                "[voice][silence]concat=n=2:v=0:a=1[out]",
                "-map",
                "[out]",
                "-c:a",
                "pcm_s16le",
                output_wav,
            ]
        else:
            cmd = [
                FFMPEG_BINARY,
                "-y",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-i",
                input_mp3,
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                output_wav,
            ]
        result = _run_subprocess(cmd)
        if result.returncode != 0:
            print(f"WARNING: WAV conversion failed, using raw mp3: {result.stderr}", file=sys.stderr)
            os.replace(input_mp3, output_wav)
    except (FileNotFoundError, OSError):
        print("WARNING: ffmpeg not found, using raw mp3", file=sys.stderr)
        os.replace(input_mp3, output_wav)


async def get_audio_duration(filepath: str) -> float:
    try:
        proc = await asyncio.create_subprocess_exec(
            FFPROBE_BINARY,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            filepath,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            info = json.loads(stdout)
            return float(info["format"]["duration"])
    except (FileNotFoundError, OSError, KeyError, ValueError, json.JSONDecodeError):
        pass

    file_size = os.path.getsize(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".wav":
        return (file_size - 44) / (24000 * 2)
    return file_size / 16000


def create_silence_wav(path: str, duration_seconds: float, sample_rate: int = 24000) -> None:
    frames = max(1, int(duration_seconds * sample_rate))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)


async def _generate_scene_audio_once(
    text: str,
    output_wav: str,
    output_srt: str,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
    tail_pause: float,
) -> float:
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

    return await get_audio_duration(output_wav)


async def generate_scene_audio(
    text: str,
    output_wav: str,
    output_srt: str,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
    tail_pause: float,
    retries: int,
) -> float:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return await _generate_scene_audio_once(
                text=text,
                output_wav=output_wav,
                output_srt=output_srt,
                voice=voice,
                rate=rate,
                volume=volume,
                pitch=pitch,
                tail_pause=tail_pause,
            )
        except Exception as exc:  # pragma: no cover - network retries
            last_error = exc
            if attempt >= retries:
                break
            backoff = round(math.pow(1.8, attempt - 1), 2)
            print(
                f"WARNING: TTS request failed on attempt {attempt}/{retries}: {exc}. "
                f"Retrying in {backoff:.2f}s...",
                file=sys.stderr,
            )
            await asyncio.sleep(backoff)
    assert last_error is not None
    raise last_error


def parse_srt_timestamp(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    total_ms = (
        int(hours) * 3600 * 1000
        + int(minutes) * 60 * 1000
        + int(seconds) * 1000
        + int(milliseconds)
    )
    return total_ms


def format_srt_timestamp(total_ms: int) -> str:
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    minutes = total_ms // 60_000
    total_ms %= 60_000
    seconds = total_ms // 1000
    milliseconds = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_srt(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    content = open(path, "r", encoding="utf-8").read().strip()
    if not content:
        return []
    blocks = re.split(r"\n\s*\n", content)
    entries: list[dict[str, Any]] = []
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        timing_line = lines[1] if "-->" in lines[1] else lines[0]
        if "-->" not in timing_line:
            continue
        start_raw, end_raw = [part.strip() for part in timing_line.split("-->")]
        text_lines = lines[2:] if timing_line == lines[1] else lines[1:]
        entries.append(
            {
                "start_ms": parse_srt_timestamp(start_raw),
                "end_ms": parse_srt_timestamp(end_raw),
                "text": " ".join(text_lines).strip(),
            }
        )
    return entries


def write_srt(path: str, entries: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        lines.extend(
            [
                str(index),
                f"{format_srt_timestamp(int(entry['start_ms']))} --> {format_srt_timestamp(int(entry['end_ms']))}",
                entry["text"],
                "",
            ]
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def concat_wavs(input_paths: list[str], output_path: str) -> None:
    if not input_paths:
        raise ValueError("No WAV files to concatenate")

    with wave.open(input_paths[0], "rb") as first:
        params = first.getparams()
        frames = [first.readframes(first.getnframes())]

    for wav_path in input_paths[1:]:
        with wave.open(wav_path, "rb") as wav_file:
            current = wav_file.getparams()
            if (current.nchannels, current.sampwidth, current.framerate) != (
                params.nchannels,
                params.sampwidth,
                params.framerate,
            ):
                raise ValueError("WAV parameter mismatch while concatenating")
            frames.append(wav_file.readframes(wav_file.getnframes()))

    with wave.open(output_path, "wb") as output:
        output.setparams(params)
        for frame_data in frames:
            output.writeframes(frame_data)


def relative_path(from_path: str, to_path: str) -> str:
    return os.path.relpath(to_path, os.path.dirname(os.path.abspath(from_path))).replace("\\", "/")


async def main() -> int:
    global FFMPEG_BINARY, FFPROBE_BINARY

    parser = argparse.ArgumentParser(description="Generate voiceover and subtitles for remotion-video")
    parser.add_argument("storyboard", help="Normalized storyboard JSON path")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--voice", default="auto", help="TTS voice id or auto (default: auto)")
    parser.add_argument("--rate", default=None, help="Rate override, for example --rate=\"-5%%\"")
    parser.add_argument("--volume", default=None, help="Volume override")
    parser.add_argument("--pitch", default=None, help="Pitch override")
    parser.add_argument("--pause", type=float, default=None, help="Tail pause after each narrated scene")
    parser.add_argument("--retries", type=int, default=3, help="Retry count for TTS requests (default: 3)")
    parser.add_argument("--update-storyboard", default=None, help="Write updated timing and audio paths into this storyboard JSON")
    parser.add_argument(
        "--public-dir",
        default=None,
        help="Optional Remotion public directory. If provided, merged audio and subtitle artifacts are copied into public/generated-audio/",
    )
    parser.add_argument("--ffmpeg-binary", default=FFMPEG_BINARY, help="Path to ffmpeg binary")
    parser.add_argument("--ffprobe-binary", default=FFPROBE_BINARY, help="Path to ffprobe binary")
    args = parser.parse_args()

    FFMPEG_BINARY = args.ffmpeg_binary
    FFPROBE_BINARY = args.ffprobe_binary

    storyboard = load_json(args.storyboard)
    scenes = storyboard.get("scenes", []) if isinstance(storyboard.get("scenes"), list) else []
    if not scenes:
        print("ERROR: storyboard has no scenes", file=sys.stderr)
        return 1

    os.makedirs(args.output_dir, exist_ok=True)
    base_tts_config = resolve_tts_config(storyboard, args)
    print("Resolved TTS profile:")
    print(
        "  "
        f"profile={base_tts_config['profile']} voice={base_tts_config['voice']} "
        f"rate={base_tts_config['rate']} volume={base_tts_config['volume']} "
        f"pitch={base_tts_config['pitch']} pause={base_tts_config['pause']:.2f}s"
    )
    print(f"  reason={base_tts_config['reason']}")

    manifest: dict[str, Any] = {
        "title": storyboard.get("meta", {}).get("title", ""),
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
        "scenes": [],
    }

    merged_srt_entries: list[dict[str, Any]] = []
    merged_caption_entries: list[dict[str, Any]] = []
    scene_wavs: list[str] = []
    cursor_ms = 0

    for index, scene in enumerate(scenes, start=1):
        scene_id = scene.get("id") or f"s{index:02d}"
        narration = (scene.get("narration") or "").strip()
        scene_tts_config = merge_tts_config(base_tts_config, scene.get("tts"))
        wav_path = os.path.join(args.output_dir, f"scene_{index:03d}.wav")
        srt_path = os.path.join(args.output_dir, f"scene_{index:03d}.srt")

        if narration:
            print(
                f"Generating scene {index}/{len(scenes)}: {scene_id} "
                f"[{scene_tts_config['voice']}, {scene_tts_config['rate']}]"
            )
            duration = await generate_scene_audio(
                narration,
                wav_path,
                srt_path,
                scene_tts_config["voice"],
                scene_tts_config["rate"],
                scene_tts_config["volume"],
                scene_tts_config["pitch"],
                scene_tts_config["pause"],
                args.retries,
            )
        else:
            duration = float(scene.get("duration_sec", 1.0) or 1.0)
            create_silence_wav(wav_path, duration)
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write("")
            print(f"Scene {index}/{len(scenes)}: {scene_id} has no narration, generated silence {duration:.2f}s")

        scene_entries = parse_srt(srt_path)
        shifted_entries = []
        for entry in scene_entries:
            shifted = {
                "start_ms": entry["start_ms"] + cursor_ms,
                "end_ms": entry["end_ms"] + cursor_ms,
                "text": entry["text"],
                "scene_id": scene_id,
            }
            shifted_entries.append(shifted)
            merged_caption_entries.append(shifted)

        merged_srt_entries.extend(shifted_entries)
        actual_start_sec = round(cursor_ms / 1000.0, 2)
        actual_duration_sec = round(duration, 2)
        cursor_ms += int(round(duration * 1000))

        manifest["scenes"].append(
            {
                "scene_id": scene_id,
                "audio": os.path.basename(wav_path),
                "srt": os.path.basename(srt_path),
                "duration_sec": actual_duration_sec,
                "start_sec": actual_start_sec,
                "tts": {
                    "voice": scene_tts_config["voice"],
                    "rate": scene_tts_config["rate"],
                    "volume": scene_tts_config["volume"],
                    "pitch": scene_tts_config["pitch"],
                    "pause": round(scene_tts_config["pause"], 2),
                },
            }
        )
        scene_wavs.append(wav_path)
        print(f"  -> {duration:.2f}s")

    voiceover_path = os.path.join(args.output_dir, "voiceover.wav")
    subtitles_path = os.path.join(args.output_dir, "subtitles.srt")
    captions_path = os.path.join(args.output_dir, "captions.json")
    manifest_path = os.path.join(args.output_dir, "manifest.json")

    concat_wavs(scene_wavs, voiceover_path)
    write_srt(subtitles_path, merged_srt_entries)
    dump_json(captions_path, {"captions": merged_caption_entries})
    manifest["total_duration_sec"] = round(cursor_ms / 1000.0, 2)
    manifest["voiceover"] = os.path.basename(voiceover_path)
    manifest["subtitles"] = os.path.basename(subtitles_path)
    manifest["captions"] = os.path.basename(captions_path)
    dump_json(manifest_path, manifest)

    public_voiceover_path = voiceover_path
    public_subtitles_path = subtitles_path
    public_captions_path = captions_path
    if args.public_dir:
        target_dir = os.path.join(os.path.abspath(args.public_dir), "generated-audio")
        os.makedirs(target_dir, exist_ok=True)
        public_voiceover_path = os.path.join(target_dir, "voiceover.wav")
        public_subtitles_path = os.path.join(target_dir, "subtitles.srt")
        public_captions_path = os.path.join(target_dir, "captions.json")
        shutil.copyfile(voiceover_path, public_voiceover_path)
        shutil.copyfile(subtitles_path, public_subtitles_path)
        shutil.copyfile(captions_path, public_captions_path)

    if args.update_storyboard:
        updated = json.loads(json.dumps(storyboard))
        audio = updated.get("audio", {}) if isinstance(updated.get("audio"), dict) else {}
        if args.public_dir:
            audio["voiceover_path"] = "generated-audio/voiceover.wav"
            audio["subtitle_path"] = "generated-audio/subtitles.srt"
        else:
            audio["voiceover_path"] = relative_path(args.update_storyboard, voiceover_path)
            audio["subtitle_path"] = relative_path(args.update_storyboard, subtitles_path)
        audio["subtitle_mode"] = "embedded"
        audio["captions"] = merged_caption_entries
        updated["audio"] = audio

        cursor_sec = 0.0
        for scene, scene_manifest in zip(updated.get("scenes", []), manifest["scenes"]):
            scene["start_sec"] = round(cursor_sec, 2)
            scene["duration_sec"] = scene_manifest["duration_sec"]
            cursor_sec += scene_manifest["duration_sec"]

        meta = updated.get("meta", {}) if isinstance(updated.get("meta"), dict) else {}
        meta["duration_sec"] = round(cursor_sec, 2)
        updated["meta"] = meta
        dump_json(args.update_storyboard, updated)
        print(f"Updated storyboard written to: {args.update_storyboard}")

    print(f"\nDone. Total duration: {manifest['total_duration_sec']:.2f}s")
    print(f"Manifest saved to: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
