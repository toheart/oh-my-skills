# Storyboard Schema

## Purpose

Use this schema when the user wants a Remotion video but the input is not yet ready to render.
Normalize rough content into this shape before building or updating compositions.

## Minimum Schema

```json
{
  "meta": {
    "title": "string",
    "aspect_ratio": "16:9",
    "fps": 30,
    "duration_sec": 90,
    "theme": "editorial-tech"
  },
  "global_style": {
    "visual_language": "string",
    "color_mood": "string",
    "typography": "string",
    "pace": "string"
  },
  "audio": {
    "voiceover_path": "optional",
    "music_path": "optional, user-supplied only",
    "subtitle_path": "optional",
    "subtitle_mode": "embedded|external|none",
    "captions": [
      {
        "start_ms": 0,
        "end_ms": 1200,
        "text": "string"
      }
    ]
  },
  "source": {
    "core_thesis": "optional",
    "audience": "optional",
    "tone": "optional",
    "tts": {
      "voice": "optional",
      "rate": "optional",
      "volume": "optional",
      "pitch": "optional",
      "pause": 0.4
    }
  },
  "scenes": [
    {
      "id": "s01",
      "start_sec": 0,
      "duration_sec": 8,
      "purpose": "string",
      "source_refs": [],
      "interpretation_note": "optional",
      "narration": "string",
      "on_screen_text": ["string"],
      "visual_role": "thesis|evidence|contrast|process|example|summary",
      "visual_type": "kinetic-type|quote|diagram|image-led|timeline|summary-list",
      "asset_refs": [],
      "visual_prompt": "string",
      "avoid": [],
      "motion_intent": "string",
      "tts": {
        "voice": "optional",
        "rate": "optional",
        "volume": "optional",
        "pitch": "optional",
        "pause": 0.4
      }
    }
  ]
}
```

## Field Semantics

### `purpose`

Why the scene exists in the argument or story.
This helps distinguish between a hook, a supporting example, a transition, and a conclusion.

### `source_refs`

Reference the source paragraphs, bullets, or note IDs that the scene comes from.
Use this when fidelity to source material matters.

### `interpretation_note`

Briefly explain how the scene interprets the source.
Use it to prevent a flashy but misleading visual translation.

### `visual_role`

Use this to identify the job the scene is doing:

- `thesis`
- `evidence`
- `contrast`
- `process`
- `example`
- `summary`

### `visual_type`

Use this to pick a rendering pattern:

- `kinetic-type`
- `quote`
- `diagram`
- `image-led`
- `timeline`
- `summary-list`

`visual_role` explains why the scene exists.
`visual_type` explains how it should be shown.

## Normalization Rules

- Convert free-form narration into one scene per clear beat.
- Keep scene durations explicit.
- Keep on-screen text short enough to read at speed.
- Add `avoid` whenever the source is conceptual and easy to stereotype visually.
- Do not let multiple scene types overlap in a way that makes the template ambiguous.
- If voiceover and captions exist, prefer real audio-driven timing over guessed scene duration.
- Preserve `subtitle_path`, `captions`, and any TTS overrides instead of dropping them during normalization.
- Leave `music_path` empty unless the user explicitly provided a music file to use.

## For Article-Like Inputs

If the input is a long article or观点, add these constraints:

- Every scene should map back to a source segment.
- Convert reading order into viewing order rather than preserving every paragraph.
- Prefer 5 to 10 scenes for short videos.
- Use `interpretation_note` whenever the visual is metaphorical rather than literal.

## Default Avoid List

If the user wants a serious, source-faithful video, consider banning these by default unless they are explicitly relevant:

- generic robot
- floating brain
- random code rain
- generic skyline
- cyber grid wallpaper
- unrelated stock footage
