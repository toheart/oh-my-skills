# Template System

## Purpose

Use this reference to choose a small, reusable set of Remotion scene templates.

## Default Template Family

For a first implementation, prefer a restrained editorial system with these scene types:

- `ThesisScene`
- `QuoteScene`
- `DiagramScene`
- `ImageLedScene`
- `TimelineScene`
- `SummaryListScene`

This keeps the system expressive enough for explainers without making every render path unique.
The bundled starter template already implements this family in `assets/starter-template/src/StoryboardVideo.tsx`.

## Mapping Rules

| storyboard visual_type | recommended component |
| --- | --- |
| `kinetic-type` | `ThesisScene` |
| `quote` | `QuoteScene` |
| `diagram` | `DiagramScene` |
| `image-led` | `ImageLedScene` |
| `timeline` | `TimelineScene` |
| `summary-list` | `SummaryListScene` |

## Composition Strategy

Prefer one of these approaches:

### Option A: Single master composition

Use one composition that renders an ordered array of scenes.
This is the best default when the skill is fed a normalized storyboard.

Good for:

- one-off videos from structured input
- batch rendering with different props
- keeping the render contract stable
- the bundled starter template

### Option B: Template-family compositions

Maintain a few high-level compositions for distinct product families, such as:

- editorial explainer
- quote-led social cut
- timeline explainer

Good for:

- teams with repeated output formats
- clearer visual constraints per format

## Design Bias

Prefer scenes that communicate argument structure clearly over scenes that merely add motion.
Do not collapse every `visual_type` into the same card layout with only color changes.
The whole point of the template family is to preserve a stable render contract while still giving different scene roles distinct compositions.

Good uses of motion:

- revealing hierarchy
- sequencing steps
- emphasizing contrast
- pacing narration

Bad uses of motion:

- movement with no semantic role
- transitions that distract from reading
- too many visual motifs in one short video

## Renderer Rules

Keep one shared visual system, but let each renderer have a different composition grammar:

- `kinetic-type`: big thesis typography, high contrast, minimal supporting text
- `diagram`: cards, lanes, or logic blocks that explain relationships
- `timeline`: numbered beats or milestones with directional reading flow
- `quote`: centered statement with quotation emphasis and strong whitespace
- `summary-list`: modular takeaways rather than a paragraph pasted on screen
- `image-led`: dedicate real space to media instead of treating images as optional thumbnails

Also keep these constraints:

- narration should not automatically appear as a full paragraph in every scene
- internal planning fields such as `avoid` and `visual_prompt` are usually for generation logic, QA notes, or upstream asset generation, not for final viewer-facing UI
- subtitles need their own safe area and should not compete with scene chrome

## Narration-Synced Reveal

The starter template natively supports narration-synced element reveal via `appear_at_ms` timestamps on `on_screen_text` items.

### How It Works

1. `on_screen_text` accepts both `string` and `OnScreenTextItem` (`{text, appear_at_ms?, anchor?}`)
2. `useStaggeredItem(index, staggerMs, appearAtMs?)` checks `appearAtMs` first; if present, the element enters at that precise millisecond offset from scene start; if absent, it falls back to equal-interval staggering
3. `align_anchors.py` populates `appear_at_ms` by matching `anchor` keywords against TTS captions

### Rendering Rules

- All six scene components (Thesis, Diagram, Timeline, SummaryList, Quote, ImageLed) support `OnScreenTextItem`
- Elements with `appear_at_ms` enter via `spring()` animation at the exact frame, creating a reveal effect synchronized to the narrator speaking the corresponding phrase
- When `on_screen_text` contains plain strings (no anchors), the renderer falls back to equal-interval staggering — no code changes needed
- Do not mix anchor-synced and manually-timed `appear_at_ms` in the same scene; pick one timing source

### Data Flow

```
storyboard.json (anchor keywords in on_screen_text_anchors)
    ↓ generate_audio.py
captions.json (word-level timestamps)
    ↓ align_anchors.py
storyboard.normalized.json (on_screen_text as OnScreenTextItem[] with appear_at_ms)
    ↓ Remotion useStaggeredItem
spring animation at precise frame
```

## When To Use Companion Skills

- Use `frontend-design` when the template family needs stronger typography, layout, or visual-language definition.
- Use `webapp-testing` when you need to verify a browser preview surface or inspect rendering/debug behavior.

These are workflow helpers, not hard dependencies for rendering.
