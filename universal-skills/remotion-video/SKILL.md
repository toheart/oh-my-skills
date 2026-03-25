---
name: remotion-video
description: Render structured videos with Remotion using React and TypeScript. Use this skill whenever the user wants to generate, edit, template, batch-render, or server-side render videos with Remotion; when they already have a storyboard, scene list, narration, subtitles, or a `storyboard.json` / `video-brief.json`; or when they ask to turn structured content into a reusable motion-graphics video pipeline. Also use it when the user wants to modify an existing Remotion composition, map content into video templates, or export MP4 output from a React-based video workflow.
---

# Remotion Video

## Overview

Use this skill to turn structured video plans into Remotion projects and rendered video output.
Treat Remotion as a rendering and composition system, not as a place to guess the meaning of a long article from scratch.

The bundled scripts and starter template are the default path.
Do not rewrite normalization, project bootstrap, SSR rendering, or verification from scratch unless the current repo already has a stronger equivalent.

## Compatibility

Tested version ranges:

- **Remotion**: 4.x (4.0.365+). The bundled starter template and render script target Remotion 4 APIs. Remotion 3.x is not supported.
- **edge-tts**: 6.x–7.x (pip install edge-tts). If `SubMaker` or `Communicate.stream()` signature changes in a future release, pin to a working version.
- **Node.js**: 18+
- **Python**: 3.9+

Runtime dependencies:

- Node.js 18+
- A package manager such as `npm`, `pnpm`, or `yarn`
- Remotion 4.x packages (`remotion`, `@remotion/bundler`, `@remotion/renderer`) in the project that will render the video
- TypeScript and React support
- `ffmpeg` recommended for media inspection and output verification
- Python 3.9+ if you want to generate voiceover and subtitles using the bundled audio script
- `edge-tts` (6.x–7.x) if you want to generate voiceover and subtitles from storyboard narration

Bundled defaults are optimized for a Windows-friendly and zh-CN-friendly workflow:

- `scripts/render_video.ts` tries common Chrome paths first and then falls back to `REMOTION_BROWSER_EXECUTABLE`. It also supports `--chrome-mode` with automatic fallback between `headless-shell` and `chrome-for-testing` to handle different browser installations.
- `scripts/generate_audio.py` defaults to zh-CN Edge TTS voices unless the user explicitly overrides voice selection
- the starter template uses typography that works well for Chinese and English editorial explainers

Default BGM policy for this skill:

- do not automatically download, generate, choose, or mix background music unless the user explicitly provides a music file and asks you to use it
- if the user did not provide BGM, finish the video without `music_path`
- at the end, you may recommend a small list of online BGM candidates that fit the article's tone, so the user can add music manually later

If the user is clearly on another platform or needs another language or voice, adapt the browser executable, fonts, and TTS voice explicitly instead of assuming the defaults fit.

Optional companion skills:

- `frontend-design`: Use when the user needs help defining a visual language, typography system, scene layout direction, or a stronger design concept for the video template.
- `webapp-testing`: Use when you need to validate a local preview page, inspect rendering issues, or test a browser-based Remotion preview/debug surface.
- `article-to-storyboard`: If available, use it upstream when the input is a long article, argument, opinion piece, or notes that still need to become a structured storyboard before rendering.

Do not treat other frontend-oriented skills as hard dependencies just because Remotion uses React.
Only bring them in when the task actually benefits from their workflow.

## Default Workflow

Follow this order by default:

1. normalize and validate the storyboard contract
2. choose whether to patch an existing Remotion project or bootstrap the starter template
3. generate audio and captions when narration should drive timing
4. render through SSR with one stable props object
5. verify the output before calling the job done

If the user only wants high-level planning, you can stop earlier.
If the user wants implementation, drive the task through the full pipeline instead of giving generic advice.

## 1. Decide Whether the Input Is Ready

If the user already provides one of the following, the input is usually ready for Remotion work:

- `storyboard.json`
- `video-brief.json`
- a clear scene list with duration, narration, on-screen text, and asset requirements
- an existing Remotion project or composition to update

If the user only provides a long article, opinion piece, interview, or rough notes, do not jump directly into Remotion code.
First normalize the input into a structured storyboard using the schema in `references/storyboard-schema.md`.

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

## 2. Normalize Into a Stable Storyboard Contract

Prefer a structured intermediate format over a vague visual prompt.
For each scene, capture:

- purpose
- narration
- on-screen text
- duration
- visual role
- visual type
- asset references
- avoid list
- motion intent

If the source material is an article, keep each scene traceable back to the source text.
Include source references and a short interpretation note when useful.

Use the bundled normalizer as the default preflight step:

```bash
python scripts/normalize_storyboard.py <input.json> <workspace>/storyboard.normalized.json
```

That script is both a normalizer and a contract check.
Treat failures as upstream input problems to fix before touching Remotion code.

The normalized storyboard should become the single source of truth for:

- composition metadata
- publishing target and user-confirmed duration brief
- scene order and timing
- asset references
- subtitle expectations
- render props

Unless the user has already provided a music asset, leave `audio.music_path` empty.
Do not fill it by searching, downloading, or generating music inside this skill.

Do not fork separate timing logic across multiple files.

## 3. Choose the Composition Strategy

Read `references/template-system.md` before deciding how to build the video.
Prefer mapping scenes into a small set of reusable components instead of inventing a brand new composition for every project.

Good default scene and component pairs:

- thesis or bold claim -> `ThesisScene`
- quotation -> `QuoteScene`
- process explanation -> `DiagramScene`
- example or case study -> `ImageLedScene`
- chronology -> `TimelineScene`
- wrap-up -> `SummaryListScene`

When in doubt, keep the number of scene types small and the design language coherent.

## 4. Pick the Project Path

State which mode you are using before editing:

- `existing-project`: patch the user's repo in place and keep their conventions where possible
- `starter-template`: initialize from `assets/starter-template` and use it as the base render path

### Existing project mode

Use this when the user already has a working Remotion repo or composition.

- keep the user's existing project structure
- map the normalized storyboard into one stable prop object
- update or add a small template family instead of scattering scene-specific code
- keep content logic in props, not hardcoded JSX

### Starter template mode

Use this when the user needs a fresh project or when the existing repo is too messy to be the fastest path.

```bash
node scripts/init_project.mjs <target-project-dir>
```

Then install dependencies in the target project and use the starter composition `RemotionVideo`.
The bundled template already implements the default scene family and `calculateMetadata` logic, so prefer extending it instead of rebuilding the render shell from zero.

For `existing-project`, avoid copying the starter template wholesale into a mature repo unless the user explicitly wants a reset.
For `starter-template`, keep media in a predictable public path and keep props JSON outside the source tree when possible.

## 5. Implement the Remotion Render Path

Follow the SSR flow described in `references/remotion-ssr.md`:

1. prepare or open the Remotion project
2. bundle the project
3. select the composition and calculate metadata
4. pass the same normalized props into rendering
5. render the media output

Keep dynamic inputs in props rather than scattering logic across many hardcoded files.

The default SSR entrypoint is:

```bash
npx tsx scripts/render_video.ts \
  --entry <project>/src/index.ts \
  --props <workspace>/storyboard.normalized.json \
  --composition RemotionVideo \
  --out <workspace>/output/final.mp4
```

Reuse `scripts/render_video.ts` unless the repo already has a stronger SSR harness.
Its job is to keep bundling, composition selection, and rendering fed by the same normalized props file.

## 6. Generate Voiceover and Subtitles When Needed

If the user needs generated voiceover and subtitles, use `scripts/generate_audio.py` before rendering.
That script updates the storyboard with actual timing, a merged voiceover path, and inline captions for embedded subtitle rendering.

Edge TTS is the default low-friction provider, but the audio contract is intentionally provider-agnostic.
You can swap in a better TTS backend later as long as it still outputs the same merged voiceover and caption artifacts.

Default audio flow:

```bash
python scripts/generate_audio.py \
  <workspace>/storyboard.normalized.json \
  <workspace>/audio \
  --public-dir <project>/public \
  --update-storyboard <workspace>/storyboard.normalized.json
```

Use `--public-dir` when the Remotion composition should load generated media via `staticFile()`.
If the user already has a trusted voiceover file, preserve it and do not regenerate audio just because narration text exists.

Do not treat BGM as part of this automatic audio step.
This skill's built-in automation is for narration and subtitles.
Background music is user-supplied only.

## 7. Verify Output

After rendering, check:

- output resolution and aspect ratio
- duration against the storyboard plan
- audio presence and rough sync
- subtitle presence if requested
- missing media assets or fallback content

If no user-supplied BGM was provided, do not treat the absence of `music_path` as a verification problem.

If a render fails, inspect whether the root cause is:

- invalid storyboard input
- missing media assets
- composition logic mismatch
- runtime dependency mismatch

Read `references/output-acceptance.md` before signing off on a render.
Treat audio and video sync and audio quality as release criteria, not polish.

The default verification step is:

```bash
python scripts/verify_output.py <workspace>/output/final.mp4 <workspace>/storyboard.normalized.json
```

If verification reports contract problems, fix the storyboard or media pipeline first.
Do not paper over sync issues by hand-tuning JSX timing in isolation.

## 8. Batch Rendering

For repeatable template families, use one stable composition plus a batch of props files.

- keep the composition id fixed
- vary content through storyboard JSON props
- generate one normalized storyboard per output
- run the same render and verification steps for each output

If the user wants 10 to 100 near-identical videos, the right optimization target is the props pipeline, not more bespoke scene components.

## Input Contract

The preferred input is a structured JSON document.
Use `references/storyboard-schema.md` as the source of truth.

At minimum, aim to have:

- project metadata
- required planning metadata
- global style guidance
- audio and subtitle expectations
- an ordered list of scenes with timing and visual intent

If the user gives only partial structure, normalize it before rendering.

If BGM is not explicitly provided by the user, keep `audio.music_path` unset and add BGM recommendations in the final write-up instead of mutating the render contract.

## Design Guidance

Remotion can render flashy motion quickly, but that does not mean the video should be visually noisy.
Keep these principles:

- match the visual system to the content type
- prefer semantic scene roles over decorative motion
- use explicit `avoid` lists to prevent generic AI imagery when the source is conceptual
- keep typography, spacing, and motion consistent across scenes
- reuse a template family whenever possible

If the user says the generated video does not feel faithful to the source material, the likely fix is upstream storyboard quality, not more random visual detail.

## Long-Form Source Material

When the input is a long article or argument and no upstream storyboard skill is available, do this before coding:

1. collect and confirm the required planning metadata block
2. extract the central thesis
3. identify the audience and target duration
4. convert the reading structure into a watching structure
5. break the piece into scenes
6. assign each scene a visual role and visual type
7. add `avoid` constraints for misleading imagery

Do not reduce an article to a single free-form video prompt.

## References

Read these files as needed:

- `assets/starter-template/`: bundled Remotion starter project for fresh builds or controlled rewrites
- `references/remotion-ssr.md`: Remotion server-side rendering flow and implementation notes
- `references/storyboard-schema.md`: input schema and normalization guidance
- `references/template-system.md`: recommended component families and mapping rules
- `references/audio-pipeline.md`: bundled voiceover and subtitle generation flow
- `references/output-acceptance.md`: render acceptance criteria for sync and audio quality

Use these scripts by default instead of recreating their logic:

- `scripts/init_project.mjs`: copy the starter template into a new target project
- `scripts/normalize_storyboard.py`: normalize and validate structured input
- `scripts/generate_audio.py`: generate voiceover, subtitles, and audio-driven timing
- `scripts/render_video.ts`: run the shared SSR render path
- `scripts/verify_output.py`: verify duration, audio alignment, and subtitle timing

## BGM Recommendation Policy

When the user wants help with music but has not provided a file:

- infer the music direction from the article tone, audience, and pacing
- search the web for a few suitable BGM candidates from legitimate music libraries
- return a short recommendation list with title, source site, and why each one fits
- do not download or mix the music unless the user later provides a chosen file and explicitly asks for integration
