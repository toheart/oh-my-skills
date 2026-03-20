# Remotion SSR

## Purpose

Use this reference when implementing or reviewing the actual Remotion render path.

## Core Flow

Remotion server-side rendering is easiest to reason about as a five-step pipeline:

1. Prepare a Remotion project with compositions
2. Bundle the project
3. Select the target composition
4. Calculate metadata and normalize dynamic props
5. Render media output

The important implementation rule is consistency:

- Use one normalized input object
- Pass the same props into composition selection and final rendering
- Keep timing decisions derived from the same source of truth

## Recommended Mental Model

Treat the Remotion app as a template library, not as a free-form code dump.
The bundle is the compiled template set.
The storyboard is the structured content payload.
The render step combines the two.

## Practical Notes

- Keep each composition focused on a template family rather than a single one-off video.
- Prefer composition props over hardcoded scene text.
- Normalize all durations before rendering so scene timing is stable.
- If subtitles or voiceover exist, use them to drive timing rather than guessing in JSX.
- Verify output after render instead of assuming success from a completed process exit.

## Failure Modes To Watch

- Composition metadata disagrees with storyboard timing
- Missing media assets cause blank or fallback frames
- Props differ between composition selection and final render
- The project mixes template logic and content logic in a way that is hard to debug

## Implementation Bias

Prefer:

- a small number of reusable compositions
- a stable prop schema
- deterministic mapping from scene type to component

Avoid:

- inventing a new composition structure for every task
- mixing source article analysis directly into render logic
- relying on vague prompt text instead of a normalized scene model
