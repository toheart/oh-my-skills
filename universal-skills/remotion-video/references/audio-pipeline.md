# Audio Pipeline

## Purpose

Use this reference when generating voiceover and subtitles directly inside remotion-video.
This reference does not cover background music selection or automatic BGM mixing.

## Implementation Choice

This skill copies the audio-generation pattern into its own `scripts/generate_audio.py`
instead of depending on `article-to-video` at runtime.

The copied pipeline keeps the same core bias:

- generate speech with Edge TTS
- convert to WAV as the main intermediate format
- avoid repeated lossy re-encoding
- derive captions from real timing events
- update storyboard timing from actual audio duration

It intentionally does not:

- search for BGM online
- download music automatically
- decide final music style on the user's behalf

## Default vs Better Voices

The bundled default uses Edge TTS (tested with edge-tts 6.x–7.x) because it is easy to install, fast to run, and good enough for workflow validation.
For higher-stakes production voice quality, keep the same artifact contract but consider swapping only the speech provider:

- OpenAI or Azure neural TTS when you want a stronger baseline voice with API-backed stability
- ElevenLabs when voice naturalness matters more than cost and you can accept an external dependency
- a self-hosted model such as CosyVoice or Fish Speech when you need more control over voice style, language, or deployment

The important design rule is: keep the output contract stable.
Regardless of provider, still emit:

- merged `voiceover.wav`
- merged `subtitles.srt`
- merged `captions.json`
- updated scene timing written back to the storyboard

That lets the Remotion rendering layer stay unchanged while the speech layer improves.

## Why WAV First

WAV is used as the stable intermediate because repeated MP3 transcodes make it easier to introduce:

- audible artifacts
- encoder delay
- timing drift

The final video can still encode to AAC, but the main editing and concatenation path should stay lossless as long as possible.

## Output Artifacts

`scripts/generate_audio.py` produces:

- per-scene WAV
- per-scene SRT
- merged `voiceover.wav`
- merged `subtitles.srt`
- merged `captions.json`
- `manifest.json`

If `--update-storyboard` is used, it also writes back:

- `audio.voiceover_path`
- `audio.subtitle_path`
- `audio.subtitle_mode`
- `audio.captions`
- scene durations and starts based on actual audio

The normalized contract may also carry optional TTS overrides:

- `source.tts` for project-level defaults
- `scenes[].tts` for per-scene voice or pacing adjustments

Normalization should preserve these fields so audio generation remains configurable after preflight.

## Acceptance Bias

Always treat audio generation as part of sync correctness.
The goal is not only to get a voice file, but to produce a timing source the renderer can trust.

If the user later wants background music, that should come from a separate user-supplied file.
The skill may recommend candidates, but it should not auto-attach them during this pipeline.
