---
name: article-to-storyboard
description: Turn articles, opinion pieces, interviews, notes, outlines, and other long-form source material into structured video storyboards. Use this skill whenever the user wants to convert a written argument or document into a scene-by-scene video plan, extract the central thesis and supporting structure, generate narration and on-screen text, or produce a `storyboard.json` / `video-brief.json` that can be handed to a downstream video renderer such as Remotion. Also use it when the user says the current video prompt is too vague, the visuals do not match the article, or they need a faithful content-to-video planning step before rendering.
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

## Workflow

### 1. Read the Source for Meaning, Not Surface Topic

Start by identifying:

- the central thesis
- the intended audience
- the author's argument structure
- the most important facts, examples, tensions, and contrasts
- what must be preserved for the video to still feel faithful

If the source is messy, normalize it into sections or beats before writing any storyboard output.

### 2. Convert Reading Structure Into Watching Structure

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

### 3. Define Scene Roles Before Visual Details

For each scene, decide its job first:

- thesis
- evidence
- contrast
- process
- example
- summary

Then choose how it should appear on screen.
Do not jump straight from article text to decorative visuals.

### 4. Generate a Structured Storyboard

Use the schema in `references/storyboard-output.md`.
For each scene, include at least:

- purpose
- source references
- interpretation note when needed
- narration
- on-screen text
- visual role
- visual type
- visual prompt
- avoid list
- motion intent
- duration

Do not automatically assign or download BGM as part of the storyboard contract.
If the user wants music help, add a separate recommendation note at the end with a few online BGM directions or candidate tracks, and leave final music choice to the user.

If the video should stay faithful to the source, make every scene traceable back to the original material.

### 5. Add Visual Constraints

This step is what prevents generic or off-topic imagery.
For each scene, be explicit about:

- what the image or motion should communicate
- whether the scene is literal or metaphorical
- what imagery should be avoided
- why the chosen visual matches the source material

If the source is conceptual, an `avoid` list is usually required.

### 6. Produce Renderer-Ready Output

The final deliverable should normally be one of:

- `storyboard.json`
- `video-brief.json`
- a clearly structured scene list that can be normalized into JSON

Optional companion deliverable:

- `bgm_recommendations`: a short human-readable list of recommended online tracks or search directions based on the article's tone

If a downstream renderer is known, bias the output toward its input contract.
For `remotion-video`, keep the structure stable and machine-friendly.

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
