#!/usr/bin/env python3
"""
Verification for a rendered video against the normalized storyboard contract.

Acceptance goals:
1. No meaningful audio / video sync drift
2. No output duration mismatch against the planned storyboard
3. No obvious audio quality problems such as near-silence, clipping, or suspiciously weak encoding

Usage:
    python verify_output.py <video.mp4> <storyboard.normalized.json>
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import struct
import subprocess
import sys
import tempfile
import wave
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


FFMPEG_BINARY = os.environ.get("FFMPEG_BINARY", "ffmpeg")
FFPROBE_BINARY = os.environ.get("FFPROBE_BINARY", "ffprobe")


def run_ffprobe(video_path: str) -> dict[str, Any] | None:
    try:
        result = subprocess.run(
            [
                FFPROBE_BINARY,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    return json.loads(result.stdout)


def extract_analysis_wav(input_path: str, output_wav: str) -> bool:
    try:
        result = subprocess.run(
            [
                FFMPEG_BINARY,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                input_path,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "24000",
                "-c:a",
                "pcm_s16le",
                output_wav,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False

    return result.returncode == 0 and os.path.exists(output_wav)


def expected_dimensions(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "9:16":
        return (1080, 1920)
    if aspect_ratio == "1:1":
        return (1080, 1080)
    return (1920, 1080)


def get_streams(info: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    video_stream = None
    audio_stream = None
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        if stream.get("codec_type") == "audio" and audio_stream is None:
            audio_stream = stream
    return video_stream, audio_stream


def stream_duration(stream: dict[str, Any] | None) -> float | None:
    if not stream:
        return None
    value = stream.get("duration")
    try:
        if value is not None:
            return float(value)
    except (TypeError, ValueError):
        return None
    return None


def run_ffmpeg_filter(video_path: str, filter_name: str) -> str | None:
    try:
        result = subprocess.run(
            [
                FFMPEG_BINARY,
                "-hide_banner",
                "-i",
                video_path,
                "-af",
                filter_name,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    return (result.stdout or "") + (result.stderr or "")


def resolve_optional_media_path(storyboard_path: str, media_path: str | None) -> str | None:
    if not media_path:
        return None
    if os.path.isabs(media_path):
        return media_path
    return os.path.abspath(os.path.join(os.path.dirname(storyboard_path), media_path))


def analyze_wav(path: str, window_ms: int = 100) -> dict[str, Any]:
    with wave.open(path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        total_frames = wav_file.getnframes()

        if channels != 1 or sample_width != 2:
            raise ValueError("analysis expects mono 16-bit PCM WAV input")

        window_frames = max(1, int(sample_rate * (window_ms / 1000.0)))
        total_samples = 0
        total_sum = 0
        total_sumsq = 0
        max_abs = 0
        clipping_count = 0
        zero_crossings = 0
        previous_sign = 0
        rms_windows: list[float] = []
        low_energy_windows = 0

        while True:
            raw = wav_file.readframes(window_frames)
            if not raw:
                break
            samples = struct.unpack("<" + ("h" * (len(raw) // 2)), raw)
            if not samples:
                continue

            window_sumsq = 0
            for sample in samples:
                total_samples += 1
                total_sum += sample
                total_sumsq += sample * sample
                window_sumsq += sample * sample

                abs_sample = abs(sample)
                if abs_sample > max_abs:
                    max_abs = abs_sample
                if abs_sample >= 32760:
                    clipping_count += 1

                sign = 1 if sample > 0 else -1 if sample < 0 else 0
                if sign and previous_sign and sign != previous_sign:
                    zero_crossings += 1
                if sign:
                    previous_sign = sign

            window_rms = math.sqrt(window_sumsq / len(samples)) / 32768.0
            rms_windows.append(window_rms)
            if window_rms <= 10 ** (-40 / 20):
                low_energy_windows += 1

    if total_samples <= 0:
        raise ValueError("no audio samples decoded")

    rms = math.sqrt(total_sumsq / total_samples) / 32768.0
    rms_db = 20.0 * math.log10(max(rms, 1e-12))
    peak_ratio = max_abs / 32767.0
    rms_mean = statistics.fmean(rms_windows) if rms_windows else 0.0
    rms_stdev = statistics.pstdev(rms_windows) if len(rms_windows) > 1 else 0.0
    rms_cv = (rms_stdev / rms_mean) if rms_mean > 1e-9 else 0.0

    return {
        "duration": total_frames / float(sample_rate),
        "sample_rate": sample_rate,
        "sample_count": total_samples,
        "rms_db": rms_db,
        "peak_ratio": peak_ratio,
        "clipping_ratio": clipping_count / float(total_samples),
        "dc_offset_ratio": abs(total_sum / float(total_samples)) / 32768.0,
        "zero_crossing_ratio": zero_crossings / float(max(total_samples - 1, 1)),
        "silence_window_ratio": low_energy_windows / float(max(len(rms_windows), 1)),
        "rms_cv": rms_cv,
        "rms_windows": rms_windows,
    }


def resample_series(values: list[float], points: int) -> list[float]:
    if not values or points <= 0:
        return []
    if len(values) == points:
        return list(values)

    resampled: list[float] = []
    for index in range(points):
        start = int(round(index * len(values) / points))
        end = int(round((index + 1) * len(values) / points))
        if end <= start:
            end = min(len(values), start + 1)
        bucket = values[start:end] or [values[min(start, len(values) - 1)]]
        resampled.append(statistics.fmean(bucket))
    return resampled


def pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    centered_x = [value - mean_x for value in xs]
    centered_y = [value - mean_y for value in ys]
    denominator = math.sqrt(sum(value * value for value in centered_x) * sum(value * value for value in centered_y))
    if denominator <= 1e-12:
        return None
    numerator = sum(x * y for x, y in zip(centered_x, centered_y))
    return numerator / denominator


def check_subtitles(storyboard_path: str, storyboard: dict[str, Any], expected_duration: float) -> list[str]:
    issues: list[str] = []
    audio = storyboard.get("audio", {}) if isinstance(storyboard.get("audio"), dict) else {}
    subtitle_mode = audio.get("subtitle_mode", "none")
    subtitle_path = resolve_optional_media_path(storyboard_path, audio.get("subtitle_path"))
    captions = audio.get("captions") if isinstance(audio.get("captions"), list) else []

    if subtitle_mode == "none":
        return issues

    if not captions and not subtitle_path:
        issues.append("WARN: subtitles requested but neither inline captions nor subtitle_path exist")
        return issues

    if subtitle_path and not os.path.exists(subtitle_path):
        issues.append(f"WARN: subtitle_path does not exist: {subtitle_path}")

    last_caption_end_ms = None
    if captions:
        try:
            last_caption_end_ms = max(int(caption.get("end_ms", 0) or 0) for caption in captions)
        except (TypeError, ValueError):
            issues.append("WARN: captions exist but contain invalid timing values")

    if last_caption_end_ms is not None and expected_duration > 0:
        overflow = (last_caption_end_ms / 1000.0) - expected_duration
        if overflow > 0.5:
            issues.append(
                f"ERROR: caption timing overflows expected duration by {overflow:.2f}s"
            )
        elif overflow > 0.1:
            issues.append(
                f"WARN: caption timing slightly exceeds expected duration by {overflow:.2f}s"
            )

    return issues


def check_audio_quality(video_path: str) -> list[str]:
    issues: list[str] = []
    silence_log = run_ffmpeg_filter(video_path, "silencedetect=noise=-38dB:d=3")
    volume_log = run_ffmpeg_filter(video_path, "volumedetect")
    if silence_log is None or volume_log is None:
        issues.append("WARN: ffmpeg unavailable; skipped detailed audio-quality checks")
        return issues

    for line in silence_log.splitlines():
        if "silence_duration:" in line:
            try:
                duration = float(line.split("silence_duration:")[-1].strip())
                if duration > 3.0:
                    issues.append(f"WARN: long silence detected ({duration:.2f}s)")
            except ValueError:
                continue

    mean_volume = None
    max_volume = None
    for line in volume_log.splitlines():
        line = line.strip()
        if "mean_volume:" in line:
            try:
                mean_volume = float(line.split("mean_volume:")[-1].replace(" dB", "").strip())
            except ValueError:
                pass
        if "max_volume:" in line:
            try:
                max_volume = float(line.split("max_volume:")[-1].replace(" dB", "").strip())
            except ValueError:
                pass

    if mean_volume is not None:
        if mean_volume < -38:
            issues.append(f"ERROR: mean volume too low ({mean_volume:.1f}dB)")
        elif mean_volume < -28:
            issues.append(f"WARN: mean volume is low ({mean_volume:.1f}dB)")

    if max_volume is not None and max_volume > -0.5:
        issues.append(f"WARN: max volume suggests possible clipping ({max_volume:.1f}dB)")

    return issues


def check_waveform_quality(wav_stats: dict[str, Any], label: str) -> list[str]:
    issues: list[str] = []
    rms_db = float(wav_stats.get("rms_db", -120.0))
    clipping_ratio = float(wav_stats.get("clipping_ratio", 0.0))
    dc_offset_ratio = float(wav_stats.get("dc_offset_ratio", 0.0))
    zero_crossing_ratio = float(wav_stats.get("zero_crossing_ratio", 0.0))
    silence_window_ratio = float(wav_stats.get("silence_window_ratio", 0.0))
    rms_cv = float(wav_stats.get("rms_cv", 0.0))

    if clipping_ratio >= 0.001:
        issues.append(
            f"ERROR: {label} has heavy clipping ({clipping_ratio * 100:.2f}% clipped samples)"
        )
    elif clipping_ratio >= 0.0002:
        issues.append(
            f"WARN: {label} shows light clipping ({clipping_ratio * 100:.2f}% clipped samples)"
        )

    if dc_offset_ratio >= 0.02:
        issues.append(f"WARN: {label} shows notable DC offset ({dc_offset_ratio:.3f})")

    if silence_window_ratio >= 0.9 and rms_db > -38:
        issues.append(
            f"WARN: {label} has unusually flat low-energy structure (silence_window_ratio={silence_window_ratio:.2f})"
        )

    if zero_crossing_ratio >= 0.28 and rms_cv <= 0.12 and rms_db > -28:
        issues.append(
            f"WARN: {label} waveform looks suspiciously buzz-like "
            f"(zero_crossing_ratio={zero_crossing_ratio:.2f}, rms_cv={rms_cv:.2f})"
        )

    return issues


def check_source_audio_alignment(
    video_path: str,
    storyboard_path: str,
    storyboard: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    audio = storyboard.get("audio", {}) if isinstance(storyboard.get("audio"), dict) else {}
    source_audio_path = resolve_optional_media_path(storyboard_path, audio.get("voiceover_path"))
    if not source_audio_path:
        return issues
    if not os.path.exists(source_audio_path):
        issues.append(f"WARN: voiceover_path does not exist for verification: {source_audio_path}")
        return issues

    with tempfile.TemporaryDirectory(prefix="remotion-verify-") as temp_dir:
        rendered_wav = os.path.join(temp_dir, "rendered.wav")
        source_wav = os.path.join(temp_dir, "source.wav")
        if not extract_analysis_wav(video_path, rendered_wav):
            issues.append("WARN: failed to extract rendered audio for waveform verification")
            return issues
        if not extract_analysis_wav(source_audio_path, source_wav):
            issues.append("WARN: failed to decode source voiceover for waveform verification")
            return issues

        try:
            rendered_stats = analyze_wav(rendered_wav)
            source_stats = analyze_wav(source_wav)
        except (ValueError, wave.Error):
            issues.append("WARN: waveform analysis failed for rendered or source audio")
            return issues

        issues.extend(check_waveform_quality(rendered_stats, "rendered audio"))

        duration_delta = abs(rendered_stats["duration"] - source_stats["duration"])
        if duration_delta > 0.2:
            issues.append(
                f"ERROR: rendered audio deviates from source voiceover duration by {duration_delta:.2f}s"
            )
        elif duration_delta > 0.08:
            issues.append(
                f"WARN: rendered audio differs from source voiceover duration by {duration_delta:.2f}s"
            )

        point_count = min(len(rendered_stats["rms_windows"]), len(source_stats["rms_windows"]), 120)
        if point_count >= 8:
            rendered_rms = resample_series(rendered_stats["rms_windows"], point_count)
            source_rms = resample_series(source_stats["rms_windows"], point_count)
            correlation = pearson_correlation(rendered_rms, source_rms)
            if correlation is not None:
                if correlation < 0.65:
                    issues.append(
                        f"ERROR: rendered audio envelope diverges from source voiceover (corr={correlation:.2f})"
                    )
                elif correlation < 0.82:
                    issues.append(
                        f"WARN: rendered audio envelope only loosely matches source voiceover (corr={correlation:.2f})"
                    )

    return issues


def main() -> int:
    global FFMPEG_BINARY, FFPROBE_BINARY
    parser = argparse.ArgumentParser(description="Verify remotion-video render output.")
    parser.add_argument("video", help="Rendered video path")
    parser.add_argument("storyboard", help="Normalized storyboard JSON path")
    parser.add_argument(
        "--ffmpeg-binary",
        default=FFMPEG_BINARY,
        help="Path to ffmpeg binary; can also be set via FFMPEG_BINARY",
    )
    parser.add_argument(
        "--ffprobe-binary",
        default=FFPROBE_BINARY,
        help="Path to ffprobe binary; can also be set via FFPROBE_BINARY",
    )
    args = parser.parse_args()
    FFMPEG_BINARY = args.ffmpeg_binary
    FFPROBE_BINARY = args.ffprobe_binary

    if not os.path.exists(args.video):
        print("ERROR: video file does not exist", file=sys.stderr)
        return 1
    if not os.path.exists(args.storyboard):
        print("ERROR: storyboard file does not exist", file=sys.stderr)
        return 1

    storyboard = load_json(args.storyboard)
    info = run_ffprobe(args.video)
    if info is None:
        print("WARN: ffprobe unavailable or failed; cannot verify media metadata")
        return 0

    video_stream, audio_stream = get_streams(info)
    issues: list[str] = []

    if video_stream is None:
        issues.append("FATAL: no video stream found")
    else:
        expected_width, expected_height = expected_dimensions(
            storyboard.get("meta", {}).get("aspect_ratio", "16:9")
        )
        actual_width = int(video_stream.get("width", 0))
        actual_height = int(video_stream.get("height", 0))
        if (actual_width, actual_height) != (expected_width, expected_height):
            issues.append(
                f"WARN: dimensions are {actual_width}x{actual_height}, expected "
                f"{expected_width}x{expected_height}"
            )

    if audio_stream is None:
        issues.append("WARN: no audio stream found")
    else:
        sample_rate = int(audio_stream.get("sample_rate", 0) or 0)
        bitrate = int(audio_stream.get("bit_rate", 0) or 0)
        codec = str(audio_stream.get("codec_name", "") or "")
        if codec and codec != "aac":
            issues.append(f"WARN: audio codec is {codec}, expected aac for the default pipeline")
        if sample_rate and sample_rate < 44100:
            issues.append(f"WARN: audio sample rate is low ({sample_rate}Hz)")
        if bitrate and bitrate < 96000:
            issues.append(f"WARN: audio bitrate is low ({bitrate}bps)")

    expected_duration = float(storyboard.get("meta", {}).get("duration_sec", 0) or 0)
    actual_duration = float(info.get("format", {}).get("duration", 0) or 0)
    if expected_duration > 0 and actual_duration > 0:
        delta = abs(expected_duration - actual_duration)
        if delta > 0.75:
            issues.append(
                f"WARN: duration mismatch expected={expected_duration:.2f}s "
                f"actual={actual_duration:.2f}s delta={delta:.2f}s"
            )

    video_duration = stream_duration(video_stream)
    audio_duration = stream_duration(audio_stream)
    if video_duration is not None and audio_duration is not None:
        av_delta = abs(video_duration - audio_duration)
        if av_delta > 0.2:
            issues.append(
                f"ERROR: audio/video stream drift too high video={video_duration:.2f}s "
                f"audio={audio_duration:.2f}s delta={av_delta:.2f}s"
            )
        elif av_delta > 0.08:
            issues.append(
                f"WARN: minor audio/video stream drift video={video_duration:.2f}s "
                f"audio={audio_duration:.2f}s delta={av_delta:.2f}s"
            )

    issues.extend(check_audio_quality(args.video))
    issues.extend(check_source_audio_alignment(args.video, args.storyboard, storyboard))
    issues.extend(check_subtitles(args.storyboard, storyboard, expected_duration))

    scene_count = len(storyboard.get("scenes", []))
    print(f"Verified file: {args.video}")
    print(f"Scene count: {scene_count}")
    print(f"Expected duration: {expected_duration:.2f}s")
    if actual_duration > 0:
        print(f"Actual duration: {actual_duration:.2f}s")

    if issues:
        for issue in issues:
            print(issue)
        if any(issue.startswith(("FATAL:", "ERROR:")) for issue in issues):
            return 1
    else:
        print("OK: no verification issues detected")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
