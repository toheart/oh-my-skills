# Storyboard Schema

## Purpose

Use this schema when the user wants a Remotion video but the input is not yet ready to render.
Normalize rough content into this shape before building or updating compositions.

## Minimum Schema

```json
{
  "meta": {
    "title": "string",
    "publishing_target": "bilibili",
    "aspect_ratio": "16:9",
    "fps": 30,
    "target_duration_sec": 180,
    "duration_sec": 180,
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
    "audience": "general professional audience",
    "tone": "optional",
    "content_mode": "explainer",
    "success_metric": "argument-completeness",
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
      "on_screen_text": ["string or OnScreenTextItem"],
      "on_screen_text_anchors": [
        {
          "text": "same as on_screen_text entry",
          "anchor": "keyword from narration"
        }
      ],
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

### `meta.publishing_target`

Keep the destination platform explicit all the way into the render contract.
Do not drop it during normalization, because pacing and packaging decisions should stay inspectable downstream.

### `meta.aspect_ratio`

Treat this as user-confirmed planning metadata, not a renderer guess.

### `meta.target_duration_sec`

Use this for the user-confirmed target brief.
Keep it separate from `meta.duration_sec` so the original target survives even if audio timing later adjusts the final runtime.

### `meta.duration_sec`

Use this as the actual normalized render duration after scene timing has been resolved.

### `purpose`

Why the scene exists in the argument or story.
This helps distinguish between a hook, a supporting example, a transition, and a conclusion.

### `source_refs`

Reference the source paragraphs, bullets, or note IDs that the scene comes from.
Use this when fidelity to source material matters.

### `interpretation_note`

Briefly explain how the scene interprets the source.
Use it to prevent a flashy but misleading visual translation.

### `source.audience`

Required.
Use it to keep pacing, terminology, and exposition density aligned with the intended viewer.

### `source.content_mode`

Required.
Typical values:

- `short-read`
- `explainer`
- `deep-dive`

### `source.success_metric`

Required.
State what the video is optimizing for, such as finish rate, save value, argument completeness, or conversion.

### `on_screen_text` (extended form)

When the storyboard uses narration-synced timing, `on_screen_text` entries can be objects instead of plain strings:

```json
{
  "text": "200 题抽 50 · 80 分通过",
  "appear_at_ms": 14247,
  "anchor": "题库一共200题"
}
```

- `text`: the display string
- `appear_at_ms`: milliseconds relative to scene start when the element should enter the screen; computed by `scripts/align_anchors.py` after TTS captions are generated
- `anchor`: a keyword or phrase from the narration text used to locate the corresponding caption timestamp

The renderer's `useStaggeredItem` hook consumes `appear_at_ms` to trigger spring-based entry animations at the exact moment the narrator speaks the matching phrase.

Plain strings remain valid and will use equal-interval staggering as a fallback.

### `on_screen_text_anchors`

An optional companion field that pairs each `on_screen_text` entry with a narration keyword:

```json
"on_screen_text_anchors": [
  { "text": "AI 认证培训 · L1 基础", "anchor": "L1" },
  { "text": "200 题抽 50 · 80 分通过", "anchor": "题库一共200题" }
]
```

This field is consumed by `scripts/align_anchors.py` to match anchor keywords against TTS captions and compute `appear_at_ms`. After alignment, `on_screen_text` is rewritten to the extended `OnScreenTextItem` form.

The upstream `article-to-storyboard` skill generates this field by selecting a distinctive keyword from each on-screen text's corresponding narration segment.

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

- Preserve required planning metadata instead of collapsing it away during normalization.
- Convert free-form narration into one scene per clear beat.
- Keep scene durations explicit.
- Keep on-screen text short enough to read at speed.
- When narration-synced timing is desired, include `on_screen_text_anchors` with a distinctive keyword per entry so `align_anchors.py` can compute `appear_at_ms` after TTS generation.
- Add `avoid` whenever the source is conceptual and easy to stereotype visually.
- Do not let multiple scene types overlap in a way that makes the template ambiguous.
- If voiceover and captions exist, prefer real audio-driven timing over guessed scene duration.
- Preserve `subtitle_path`, `captions`, and any TTS overrides instead of dropping them during normalization.
- Leave `music_path` empty unless the user explicitly provided a music file to use.

## Fixed Planning Input Block

Before continuing, collect this exact planning block and treat every field as required:

- `meta.publishing_target`
- `meta.aspect_ratio`
- `meta.target_duration_sec`
- `source.audience`
- `source.content_mode`
- `source.success_metric`

If any field is missing, stop and request this exact block:

```text
publishing_target:
aspect_ratio:
content_mode:
target_duration_sec:
audience:
success_metric:
```

Do not silently infer or default these values from locale, platform habits, or previous projects.
If the user asks for recommendations, suggest one baseline preset, then wait for explicit confirmation before continuing.

## Recommended Baseline Presets

Use these only as recommendations, never as silent defaults:

- `bilibili-horizontal-explainer`: `publishing_target=bilibili`, `aspect_ratio=16:9`, `content_mode=explainer`, `target_duration_sec=180`, `audience=general professional audience`, `success_metric=argument-completeness`
- `douyin-vertical-short-read`: `publishing_target=douyin`, `aspect_ratio=9:16`, `content_mode=short-read`, `target_duration_sec=75`, `audience=general workplace audience`, `success_metric=finish-rate`
- `youtube-horizontal-deep-dive`: `publishing_target=youtube`, `aspect_ratio=16:9`, `content_mode=deep-dive`, `target_duration_sec=480`, `audience=knowledge-seeking general audience`, `success_metric=watch-time`

## For Article-Like Inputs

If the input is a long article or观点, add these constraints:

- Every scene should map back to a source segment.
- Convert reading order into viewing order rather than preserving every paragraph.
- Prefer 5 to 10 scenes for short videos.
- Use `interpretation_note` whenever the visual is metaphorical rather than literal.
- Preserve the article planning fields when moving into the normalized Remotion contract.

## Default Avoid List

If the user wants a serious, source-faithful video, consider banning these by default unless they are explicitly relevant:

- generic robot
- floating brain
- random code rain
- generic skyline
- cyber grid wallpaper
- unrelated stock footage
