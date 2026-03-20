# Output Acceptance

## Purpose

Use this reference after rendering to decide whether a video is acceptable to ship.

## Hard Requirements

### 1. No meaningful audio / video drift

The output video should not show noticeable mismatch between the visual track and the audio track.
As a practical automated check:

- compare video-stream duration to audio-stream duration
- compare the rendered audio track to the source `voiceover_path` when one exists
- fail if the delta is meaningfully above a tight threshold

### 2. No storyboard-to-output timing mismatch

The final output should stay close to the planned duration from the normalized storyboard.
Minor container overhead is acceptable.
Large deviation is not.

### 3. No obvious audio-quality defects

Reject or investigate output if there are signs of:

- near-silence
- clipping
- suspiciously low bitrate
- unusually low sample rate
- long unintended silence
- suspiciously buzz-like waveform structure
- artifacts that suggest an unstable encode chain

## Anti-Noise Bias

To reduce the chance of audible artifacts such as electrical-noise-like output:

- prefer WAV or other lossless source audio during intermediate steps
- avoid repeated lossy transcodes
- let the final output perform the main encode once
- keep audio bitrate comfortably above weak defaults

Automated checks cannot perfectly detect every artifact, but they should catch many risky outputs early.
Use them as a release gate, then do a short human spot-check on headphones before shipping.

## Verification Path

Use `scripts/verify_output.py` with ffmpeg and ffprobe available.
If system binaries are unavailable, pass explicit binary paths using:

- `--ffmpeg-binary`
- `--ffprobe-binary`

The verifier now checks three layers:

- container metadata and stream duration
- subtitle / caption timing against the storyboard plan
- rendered-audio waveform quality and alignment against the source voiceover, when available
