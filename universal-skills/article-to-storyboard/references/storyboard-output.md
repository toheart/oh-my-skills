# Storyboard Output

## Purpose

Use this reference as the output contract for downstream rendering.

## Minimum JSON Shape

```json
{
  "title": "string",
  "publishing_target": "bilibili",
  "aspect_ratio": "16:9",
  "content_mode": "explainer",
  "core_thesis": "string",
  "audience": "general professional audience",
  "tone": "string",
  "success_metric": "argument-completeness",
  "target_duration_sec": 180,
  "scenes": [
    {
      "scene_id": "s01",
      "purpose": "string",
      "source_refs": [],
      "interpretation_note": "optional",
      "duration_sec": 8,
      "narration": "string",
      "on_screen_text": ["string"],
      "visual_role": "thesis|evidence|contrast|process|example|summary",
      "visual_type": "kinetic-type|quote|diagram|image-led|timeline|summary-list",
      "visual_prompt": "string",
      "avoid": [],
      "motion_intent": "string"
    }
  ]
}
```

## Field Guidance

### `publishing_target`

Name the destination platform explicitly.
This is required because pacing, hook style, and scene density depend on where the video will be published.

### `aspect_ratio`

Use a concrete ratio such as `16:9` or `9:16`.
Treat it as required because layout decisions should not be guessed downstream.

### `content_mode`

State what kind of video this is.
Good defaults are:

- `short-read`
- `explainer`
- `deep-dive`

### `core_thesis`

Use one concise sentence.
This is the anchor that keeps the storyboard from drifting into disconnected scenes.

### `audience`

Describe the viewer clearly enough to judge how much context, jargon, and pacing the video can support.

### `success_metric`

State what the video should optimize for.
Examples:

- `finish-rate`
- `save-value`
- `argument-completeness`
- `conversion`

### `purpose`

State what this scene is doing in the argument.
Examples:

- introduce the claim
- show a supporting example
- create contrast
- summarize the takeaway

### `source_refs`

Point back to the source material.
This is essential when the user wants high fidelity.

### `interpretation_note`

Use when the visual is metaphorical or compressed.
Explain how the scene translates the source material.

### `narration`

Write spoken language, not prose lifted directly from the article.
It should sound natural when read aloud.

### `on_screen_text`

Keep it short and scannable.
It should reinforce the spoken line, not duplicate a paragraph.

### `visual_role`

Describe why the scene exists.

### `visual_type`

Describe how the scene should be rendered.

### `visual_prompt`

Use it as a renderer hint, not as the only source of meaning.
Keep it specific and grounded in the scene purpose.

### `avoid`

Use it to prevent generic visuals that often appear when the content is abstract.

### `motion_intent`

Describe the style of motion in plain language, such as:

- restrained reveal
- measured slide
- static hold with emphasis
- sequential build

### `target_duration_sec`

Treat this as a user-confirmed requirement, not a hidden default.
If the user has not supplied it, stop and request it before drafting the storyboard.

## Fixed Planning Input Block

Before continuing, collect this exact planning block and treat every field as required:

- `publishing_target`
- `aspect_ratio`
- `content_mode`
- `target_duration_sec`
- `audience`
- `success_metric`

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

## Output Quality Checks

Before finalizing the storyboard, verify:

- all required planning inputs are present
- the scenes form a coherent argument arc
- each scene has a clear purpose
- the visual treatment matches the content type
- there is enough source traceability
- the total duration is realistic for the chosen platform and content mode
- the pacing matches the declared success metric

## Duration Heuristics

Use these only after the required input gate is complete:

- `short-read`: 60 to 120 seconds, 5 to 9 scenes, one core claim, one or two strong examples
- `explainer`: 150 to 300 seconds, 8 to 14 scenes, more breathing room for setup and evidence
- `deep-dive`: 300 to 480 seconds, 12 or more scenes, broader evidence set or a planned multi-part split

For Bilibili horizontal explainers, `explainer` is usually the safer default than `short-read` unless the user explicitly wants a high-density cut.
