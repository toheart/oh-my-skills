# Storyboard Output

## Purpose

Use this reference as the output contract for downstream rendering.

## Minimum JSON Shape

```json
{
  "title": "string",
  "core_thesis": "string",
  "audience": "string",
  "tone": "string",
  "target_duration_sec": 90,
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

### `core_thesis`

Use one concise sentence.
This is the anchor that keeps the storyboard from drifting into disconnected scenes.

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

## Output Quality Checks

Before finalizing the storyboard, verify:

- the scenes form a coherent argument arc
- each scene has a clear purpose
- the visual treatment matches the content type
- there is enough source traceability
- the total duration is realistic

## Default Heuristic for Short Videos

For a 60 to 120 second video, a good default is:

- 5 to 9 scenes
- 6 to 15 seconds per scene
- one core claim
- one or two strong examples
- a closing synthesis
