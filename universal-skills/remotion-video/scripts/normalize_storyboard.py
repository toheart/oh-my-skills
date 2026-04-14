#!/usr/bin/env python3
"""
Normalize upstream storyboard JSON into the remotion-video input contract.

Usage:
    python normalize_storyboard.py <input.json> <output.json>

This script accepts either:
1. The article-to-storyboard output shape
2. A remotion-video-like shape that still needs defaults filled in

The normalizer also performs preflight validation so obviously bad storyboard
contracts fail before Remotion rendering starts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_FPS = 30
DEFAULT_THEME = "editorial-tech"
DEFAULT_VISUAL_LANGUAGE = "editorial motion graphics"
DEFAULT_COLOR_MOOD = "neutral"
DEFAULT_TYPOGRAPHY = "clean sans"
DEFAULT_PACE = "measured"
DEFAULT_SUBTITLE_MODE = "none"

VALID_VISUAL_ROLES = {
    "thesis",
    "evidence",
    "contrast",
    "process",
    "example",
    "summary",
}

VALID_VISUAL_TYPES = {
    "kinetic-type",
    "quote",
    "diagram",
    "image-led",
    "timeline",
    "summary-list",
}

VISUAL_TYPE_ALIASES = {
    "editorial-kinetic-typography": "kinetic-type",
    "kinetic-typography": "kinetic-type",
    "quote-scene": "quote",
    "diagram-scene": "diagram",
    "image-scene": "image-led",
    "timeline-scene": "timeline",
    "summary-scene": "summary-list",
}


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, value: dict[str, Any]) -> None:
    output_dir = os.path.dirname(os.path.abspath(path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def coerce_duration(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
        if parsed > 0:
            return round(parsed, 2)
    except (TypeError, ValueError):
        pass
    return round(fallback, 2)


def normalize_visual_type(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "kinetic-type"
    return VISUAL_TYPE_ALIASES.get(raw, raw)


def clean_optional_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return value


def normalize_audio(audio: dict[str, Any]) -> dict[str, Any]:
    captions = audio.get("captions") if isinstance(audio.get("captions"), list) else []
    return {
        "voiceover_path": audio.get("voiceover_path"),
        "music_path": audio.get("music_path"),
        "subtitle_path": audio.get("subtitle_path"),
        "subtitle_mode": audio.get("subtitle_mode", DEFAULT_SUBTITLE_MODE),
        "captions": captions,
    }


def normalize_scene(scene: dict[str, Any], index: int, start_sec: float, duration: float) -> dict[str, Any]:
    normalized_scene = {
        "id": scene.get("id") or scene.get("scene_id") or f"s{index:02d}",
        "start_sec": round(start_sec, 2),
        "duration_sec": duration,
        "purpose": scene.get("purpose", ""),
        "source_refs": ensure_list(scene.get("source_refs")),
        "interpretation_note": scene.get("interpretation_note", ""),
        "narration": scene.get("narration", ""),
        "on_screen_text": ensure_list(scene.get("on_screen_text")),
        "visual_role": scene.get("visual_role", "thesis"),
        "visual_type": normalize_visual_type(scene.get("visual_type")),
        "asset_refs": ensure_list(scene.get("asset_refs")),
        "visual_prompt": scene.get("visual_prompt", ""),
        "avoid": ensure_list(scene.get("avoid")),
        "motion_intent": scene.get("motion_intent", "restrained reveal"),
    }
    anchors = scene.get("on_screen_text_anchors")
    if isinstance(anchors, list) and anchors:
        normalized_scene["on_screen_text_anchors"] = anchors
    scene_tts = clean_optional_dict(scene.get("tts"))
    if scene_tts:
        normalized_scene["tts"] = scene_tts
    return normalized_scene


def normalize_remotion_shape(data: dict[str, Any]) -> dict[str, Any]:
    meta = data.get("meta", {}) if isinstance(data.get("meta"), dict) else {}
    global_style = (
        data.get("global_style", {}) if isinstance(data.get("global_style"), dict) else {}
    )
    audio = data.get("audio", {}) if isinstance(data.get("audio"), dict) else {}
    source = clean_optional_dict(data.get("source")) or {}
    scenes = data.get("scenes", []) if isinstance(data.get("scenes"), list) else []

    normalized_scenes = []
    cursor = 0.0
    for index, scene in enumerate(scenes, start=1):
        scene = scene if isinstance(scene, dict) else {}
        duration = coerce_duration(scene.get("duration_sec"), 8.0)
        start_sec = scene.get("start_sec")
        if start_sec is None:
            start_sec = cursor
        start_sec = coerce_duration(start_sec, cursor)
        normalized_scenes.append(normalize_scene(scene, index, start_sec, duration))
        cursor = start_sec + duration

    target_duration = coerce_duration(meta.get("target_duration_sec"), 0.0)
    requested_duration = coerce_duration(meta.get("duration_sec"), max(cursor, 1.0))
    planned_duration = target_duration if target_duration > 0 else requested_duration
    total_duration = round(max(planned_duration, cursor, 1.0), 2)

    normalized: dict[str, Any] = {
        "meta": {
            "title": clean_text(meta.get("title")) or "Untitled Video",
            "publishing_target": clean_text(meta.get("publishing_target")),
            "aspect_ratio": clean_text(meta.get("aspect_ratio")),
            "fps": int(meta.get("fps", DEFAULT_FPS)),
            "target_duration_sec": target_duration,
            "duration_sec": total_duration,
            "theme": clean_text(meta.get("theme")) or DEFAULT_THEME,
        },
        "global_style": {
            "visual_language": clean_text(global_style.get("visual_language")) or DEFAULT_VISUAL_LANGUAGE,
            "color_mood": clean_text(global_style.get("color_mood")) or DEFAULT_COLOR_MOOD,
            "typography": clean_text(global_style.get("typography")) or DEFAULT_TYPOGRAPHY,
            "pace": clean_text(global_style.get("pace")) or DEFAULT_PACE,
        },
        "audio": normalize_audio(audio),
        "scenes": normalized_scenes,
        "source": {
            "core_thesis": clean_text(source.get("core_thesis")),
            "audience": clean_text(source.get("audience")),
            "tone": clean_text(source.get("tone")),
            "content_mode": clean_text(source.get("content_mode")),
            "success_metric": clean_text(source.get("success_metric")),
        },
    }

    source_tts = clean_optional_dict(source.get("tts"))
    if source_tts:
        normalized["source"]["tts"] = source_tts

    return normalized


def normalize_article_storyboard_shape(data: dict[str, Any]) -> dict[str, Any]:
    scenes = data.get("scenes", []) if isinstance(data.get("scenes"), list) else []
    normalized_scenes = []
    cursor = 0.0

    for index, scene in enumerate(scenes, start=1):
        scene = scene if isinstance(scene, dict) else {}
        duration = coerce_duration(scene.get("duration_sec"), 8.0)
        normalized_scenes.append(normalize_scene(scene, index, cursor, duration))
        cursor += duration

    target_duration = coerce_duration(data.get("target_duration_sec"), 0.0)
    total_duration = round(max(target_duration, cursor, 1.0), 2)

    normalized: dict[str, Any] = {
        "meta": {
            "title": clean_text(data.get("title")) or "Untitled Video",
            "publishing_target": clean_text(data.get("publishing_target")),
            "aspect_ratio": clean_text(data.get("aspect_ratio")),
            "fps": int(data.get("fps", DEFAULT_FPS)),
            "target_duration_sec": target_duration,
            "duration_sec": total_duration,
            "theme": clean_text(data.get("theme")) or DEFAULT_THEME,
        },
        "global_style": {
            "visual_language": clean_text(data.get("visual_language")) or DEFAULT_VISUAL_LANGUAGE,
            "color_mood": clean_text(data.get("color_mood")) or DEFAULT_COLOR_MOOD,
            "typography": clean_text(data.get("typography")) or DEFAULT_TYPOGRAPHY,
            "pace": clean_text(data.get("pace")) or clean_text(data.get("tone")) or DEFAULT_PACE,
        },
        "audio": normalize_audio(
            {
                "voiceover_path": data.get("voiceover_path"),
                "music_path": data.get("music_path"),
                "subtitle_path": data.get("subtitle_path"),
                "subtitle_mode": data.get("subtitle_mode", DEFAULT_SUBTITLE_MODE),
                "captions": data.get("captions"),
            }
        ),
        "scenes": normalized_scenes,
        "source": {
            "core_thesis": clean_text(data.get("core_thesis")),
            "audience": clean_text(data.get("audience")),
            "tone": clean_text(data.get("tone")),
            "content_mode": clean_text(data.get("content_mode")),
            "success_metric": clean_text(data.get("success_metric")),
        },
    }

    source_tts = clean_optional_dict(data.get("tts"))
    if source_tts:
        normalized["source"]["tts"] = source_tts

    return normalized


def is_remote_asset(asset_ref: str) -> bool:
    lowered = asset_ref.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def validate_storyboard(storyboard: dict[str, Any], input_path: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    scenes = storyboard.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return ["storyboard must contain at least one scene"], warnings

    seen_ids: set[str] = set()
    previous_end = 0.0
    last_end = 0.0
    input_dir = os.path.dirname(os.path.abspath(input_path))

    for index, raw_scene in enumerate(scenes, start=1):
        if not isinstance(raw_scene, dict):
            errors.append(f"scene {index} is not an object")
            continue

        scene_id = str(raw_scene.get("id") or f"s{index:02d}")
        if scene_id in seen_ids:
            errors.append(f"duplicate scene id: {scene_id}")
        seen_ids.add(scene_id)

        try:
            start_sec = float(raw_scene.get("start_sec", 0) or 0)
            duration_sec = float(raw_scene.get("duration_sec", 0) or 0)
        except (TypeError, ValueError):
            errors.append(f"scene {scene_id} has invalid numeric timing")
            continue

        if start_sec < 0:
            errors.append(f"scene {scene_id} starts before 0s")
        if duration_sec <= 0:
            errors.append(f"scene {scene_id} must have positive duration")

        end_sec = round(start_sec + duration_sec, 2)
        if start_sec + 0.01 < previous_end:
            errors.append(
                f"scene {scene_id} overlaps the previous scene "
                f"(start={start_sec:.2f}s previous_end={previous_end:.2f}s)"
            )
        previous_end = max(previous_end, end_sec)
        last_end = max(last_end, end_sec)

        visual_role = str(raw_scene.get("visual_role") or "")
        if visual_role not in VALID_VISUAL_ROLES:
            errors.append(
                f"scene {scene_id} has unsupported visual_role '{visual_role}'"
            )

        visual_type = str(raw_scene.get("visual_type") or "")
        if visual_type not in VALID_VISUAL_TYPES:
            errors.append(
                f"scene {scene_id} has unsupported visual_type '{visual_type}'"
            )

        on_screen_text = raw_scene.get("on_screen_text")
        if not isinstance(on_screen_text, list):
            errors.append(f"scene {scene_id} must use a list for on_screen_text")
        elif not raw_scene.get("purpose") and not any(str(item).strip() for item in on_screen_text):
            warnings.append(
                f"scene {scene_id} has neither purpose nor meaningful on_screen_text"
            )

        asset_refs = raw_scene.get("asset_refs")
        if not isinstance(asset_refs, list):
            errors.append(f"scene {scene_id} must use a list for asset_refs")
        else:
            for asset_ref in asset_refs:
                if not isinstance(asset_ref, str) or not asset_ref.strip():
                    warnings.append(f"scene {scene_id} contains a blank asset reference")
                    continue
                if os.path.isabs(asset_ref) or is_remote_asset(asset_ref):
                    continue
                resolved = os.path.abspath(os.path.join(input_dir, asset_ref))
                if not os.path.exists(resolved):
                    warnings.append(
                        f"scene {scene_id} references a missing local asset: {asset_ref}"
                    )

    meta = storyboard.get("meta", {}) if isinstance(storyboard.get("meta"), dict) else {}
    publishing_target = clean_text(meta.get("publishing_target"))
    if not publishing_target:
        errors.append("meta.publishing_target is required")

    aspect_ratio = clean_text(meta.get("aspect_ratio"))
    if not aspect_ratio:
        errors.append("meta.aspect_ratio is required")

    try:
        target_duration_sec = float(meta.get("target_duration_sec", 0) or 0)
    except (TypeError, ValueError):
        errors.append("meta.target_duration_sec must be numeric")
        target_duration_sec = 0.0
    else:
        if target_duration_sec <= 0:
            errors.append("meta.target_duration_sec must be positive")

    try:
        duration_sec = float(meta.get("duration_sec", 0) or 0)
    except (TypeError, ValueError):
        errors.append("meta.duration_sec must be numeric")
    else:
        if duration_sec <= 0:
            errors.append("meta.duration_sec must be positive")
        elif duration_sec + 0.01 < last_end:
            errors.append(
                "meta.duration_sec is shorter than the final scene end "
                f"({duration_sec:.2f}s < {last_end:.2f}s)"
            )

    fps = meta.get("fps", DEFAULT_FPS)
    try:
        parsed_fps = int(fps)
    except (TypeError, ValueError):
        errors.append("meta.fps must be an integer")
    else:
        if parsed_fps <= 0:
            errors.append("meta.fps must be positive")

    source = storyboard.get("source", {}) if isinstance(storyboard.get("source"), dict) else {}
    if not clean_text(source.get("audience")):
        errors.append("source.audience is required")
    if not clean_text(source.get("content_mode")):
        errors.append("source.content_mode is required")
    if not clean_text(source.get("success_metric")):
        errors.append("source.success_metric is required")

    audio = storyboard.get("audio", {}) if isinstance(storyboard.get("audio"), dict) else {}
    subtitle_mode = str(audio.get("subtitle_mode", DEFAULT_SUBTITLE_MODE) or DEFAULT_SUBTITLE_MODE)
    captions = audio.get("captions")
    if subtitle_mode not in {"embedded", "external", "none"}:
        warnings.append(
            f"audio.subtitle_mode '{subtitle_mode}' is non-standard; expected embedded, external, or none"
        )
    if captions is not None and not isinstance(captions, list):
        errors.append("audio.captions must be a list when provided")

    return errors, warnings


def normalize(data: dict[str, Any]) -> dict[str, Any]:
    if "meta" in data and "scenes" in data:
        return normalize_remotion_shape(data)
    if "title" in data and "scenes" in data:
        return normalize_article_storyboard_shape(data)
    raise ValueError("Unsupported storyboard shape. Expected scenes plus title or meta.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize storyboard JSON for remotion-video.")
    parser.add_argument("input", help="Input storyboard JSON path")
    parser.add_argument("output", help="Output normalized JSON path")
    args = parser.parse_args()

    try:
        normalized = normalize(load_json(args.input))
        errors, warnings = validate_storyboard(normalized, args.input)
    except Exception as exc:  # pragma: no cover - simple CLI guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"WARN: {warning}", file=sys.stderr)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    dump_json(args.output, normalized)
    print(f"Normalized storyboard written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
