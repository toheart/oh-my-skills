---
name: article-to-storyboard
description: Turn articles, opinion pieces, interviews, notes, outlines, and other long-form source material into structured video storyboards. Use this skill whenever the user wants to convert a written argument or document into a scene-by-scene video plan, extract the central thesis and supporting structure, generate narration and on-screen text, or produce a `storyboard.json` / `video-brief.json` that can be handed to a downstream video renderer such as Remotion. Also use it when the user needs platform-aware storyboard planning, must lock target duration/audience/success metrics before rendering, says the current video prompt is too vague, or says the visuals do not match the article.
---

# Article To Storyboard

## Overview

Use this skill to transform long-form written material into a structured, source-faithful storyboard for video production.
The goal is not to produce a vague visual prompt, but to generate a stable intermediate contract that a renderer can consume.

## Compatibility

This skill has no special runtime dependency beyond normal text analysis and file handling.

Optional companion skills:

- `remotion-video`: Use downstream when the storyboard should be rendered as a Remotion video.
- `frontend-design`: Use when the user wants help shaping the visual language of the resulting scene system.
- `article-to-video`: If the user explicitly wants a PPT-style explainer workflow instead of a Remotion-style render pipeline, hand the structured output into that path instead.

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
If the source material itself is missing, ask for it separately before storyboarding.

## Recommended Baseline Presets

Use these only as recommendations, never as silent defaults:

- `bilibili-horizontal-explainer`: `publishing_target=bilibili`, `aspect_ratio=16:9`, `content_mode=explainer`, `target_duration_sec=180`, `audience=general professional audience`, `success_metric=argument-completeness`
- `douyin-vertical-short-read`: `publishing_target=douyin`, `aspect_ratio=9:16`, `content_mode=short-read`, `target_duration_sec=75`, `audience=general workplace audience`, `success_metric=finish-rate`
- `youtube-horizontal-deep-dive`: `publishing_target=youtube`, `aspect_ratio=16:9`, `content_mode=deep-dive`, `target_duration_sec=480`, `audience=knowledge-seeking general audience`, `success_metric=watch-time`

## Workflow

### 1. Enforce the Input Gate

Verify that all required planning inputs are present before reading or compressing the source.
If the user says only "make this for Bilibili" or only gives a duration, pause and request the remaining required fields.

### 2. Read the Source for Meaning, Not Surface Topic

Start by identifying:

- the central thesis
- the intended audience
- the author's argument structure
- the most important facts, examples, tensions, and contrasts
- what must be preserved for the video to still feel faithful

If the source is messy, normalize it into sections or beats before writing any storyboard output.

### 3. Convert Reading Structure Into Watching Structure

A good article is not automatically a good video.
Rewrite the material into a viewing sequence, usually something like:

1. hook
2. claim
3. development
4. evidence or example
5. contrast or tension
6. conclusion

Do not preserve paragraph order blindly if the video becomes flatter as a result.
Preserve meaning, not formatting.

### 4. Define Scene Roles Before Visual Details

For each scene, decide its job first:

- thesis
- evidence
- contrast
- process
- example
- summary

Then choose how it should appear on screen.
Do not jump straight from article text to decorative visuals.

### 5. Generate a Structured Storyboard

Use the schema in `references/storyboard-output.md`.
Preserve the required planning inputs at the top level of the storyboard or brief so downstream tools and human reviewers can see what the plan is optimizing for.
For each scene, include at least:

- purpose
- source references
- interpretation note when needed
- narration
- on-screen text
- on-screen text anchors (when downstream rendering will use narration-synced timing)
- visual role
- visual type
- visual prompt
- avoid list
- motion intent
- duration

Do not automatically assign or download BGM as part of the storyboard contract.
If the user wants music help, add a separate recommendation note at the end with a few online BGM directions or candidate tracks, and leave final music choice to the user.

If the video should stay faithful to the source, make every scene traceable back to the original material.

### 5b. Add Narration Anchors for Synced Entry Animations

When the downstream renderer is `remotion-video` and the video will use TTS-generated narration, add `on_screen_text_anchors` to each scene. This enables narration-synced staggered reveal animations where each visual element enters the screen at the exact moment the narrator speaks the corresponding phrase.

For each `on_screen_text` entry, include a companion anchor:

```json
"on_screen_text": ["200 题抽 50 · 80 分通过"],
"on_screen_text_anchors": [
  { "text": "200 题抽 50 · 80 分通过", "anchor": "题库一共200题" }
]
```

Choose anchors that are:

- distinctive keywords or short phrases from the scene's narration
- unique within the scene (appear exactly once in narration text)
- nouns, numbers, or domain terms rather than common filler words

The downstream `remotion-video` skill uses these anchors to match against TTS caption timestamps and compute precise `appear_at_ms` values. If anchors are not provided, the renderer falls back to equal-interval staggering.

See `references/storyboard-output.md` for the full field specification.

### 6. Add Visual Constraints

This step is what prevents generic or off-topic imagery.
For each scene, be explicit about:

- what the image or motion should communicate
- whether the scene is literal or metaphorical
- what imagery should be avoided
- why the chosen visual matches the source material

If the source is conceptual, an `avoid` list is usually required.

### 7. Produce Renderer-Ready Output

The final deliverable should normally be one of:

- `storyboard.json`
- `video-brief.json`
- a clearly structured scene list that can be normalized into JSON

Optional companion deliverable:

- `bgm_recommendations`: a short human-readable list of recommended online tracks or search directions based on the article's tone

If a downstream renderer is known, bias the output toward its input contract.
For `remotion-video`, keep the structure stable and machine-friendly, and include `on_screen_text_anchors` so the renderer can align visual entry animations to TTS narration timestamps.

## Fidelity Rules

If the user says the video must feel faithful to the article, follow these rules:

- Keep each scene grounded in a source reference
- Distinguish fact, claim, example, and metaphor
- Prefer semantic scene roles over aesthetic flourish
- Avoid stock visual clichés unless the source explicitly supports them
- Make the relationship between source and scene explainable

The most common failure mode is not weak wording.
It is skipping the semantic middle layer between article and rendering.

## Long-Form Inputs

Use this skill when the input is any of the following:

- article draft
- blog post
- essay
- viewpoint memo
- interview transcript
- talk outline
- meeting notes with a strong argument thread

If the user only wants a summary, do not overproduce a storyboard.
Use this skill when the target output is video planning, not general summarization.

## Deliverable Shapes

Choose the lightest output that still supports the next step:

- For brainstorming: a compact video brief
- For real production: a full `storyboard.json`
- For teams collaborating with design or motion: storyboard plus interpretation notes and visual constraints

## References

Read these files as needed:

- `references/reading-workflow.md`: How to extract thesis, structure, and transferable beats from long-form writing
- `references/storyboard-output.md`: The target output schema and field semantics
- `references/visual-translation.md`: How to turn ideas into visuals without drifting into generic imagery
