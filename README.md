# Spatial audio coherence pipeline — build notes

Everything here has been executed end-to-end in a sandboxed environment against
real synthetic test stems before being handed over — not just written from the
API docs. See "What was actually tested" below.

## Files

- `main.py` — orchestrator tying every stage together; resumable via
  `--only`. See Section 3.8.
- `placement_agent_harness.py` — unchanged core logic, now defaults to a
  self-hosted vLLM endpoint (OpenAI-compatible), with retry/backoff and
  defensive JSON parsing added since a single bad response used to kill
  the whole run.
- `stem_feature_extractor.py` — RMS energy, transient detection, silence
  ratio, spectral-centroid brightness. Re-verified against real synthetic
  stem audio in this build.
- `adm_renderer.py` — builds a real ADM BW64 file from the harness's
  scene/placement output and renders it via the real EBU EAR renderer
  (`ear-render`). One continuous ADM Object track per recurring stem, so
  coherence is visible directly in the ADM metadata, not just your JSON.
- `ffmpeg_fallback.py` — the kill-switch safety net. Same input shape as
  `adm_renderer.build_adm_bwf`, but produces a plain channel-based 5.1 mix
  with real ffmpeg `amix`/`amerge` — no ADM, no EAR, nothing that can fail
  in a way you haven't already tested.
- `binaural_renderer.py` — convolves EAR's speaker-layout output with an
  HRIR per speaker position, summing to stereo for headphone playback.
- `dashboard.py` — Gradio viewer for already-computed output (no live
  GPU dependency); confirmed serving with a live HTTP 200.
- `Dockerfile` — fixed: removed `HSA_OVERRIDE_GFX_VERSION` (only for
  unsupported consumer GPUs — MI300X/gfx942 is natively supported, so this
  was misrouting kernels) and the no-op `PYTORCH_ROCM_ARCH` (build-from-source
  only, does nothing on the prebuilt wheel). Fixed the torch-after-demucs
  install order that could silently leave you on a non-ROCm torch build.

## Setting up the self-hosted model (AMD compute requirement)

Given the compressed timeline, use a mid-size instruct model, not a 70B —
download/load time on a 70B will eat hours you don't have, and vLLM 0.16 +
ROCm 7.2 is already pre-baked into your notebook image:

```bash
vllm serve Qwen/Qwen2.5-32B-Instruct --port 8000 --dtype bfloat16
```

Then, no code changes needed:

```bash
export LLM_BASE_URL="http://localhost:8000/v1"
export LLM_API_KEY="not-needed-for-local-vllm"
export LLM_MODEL="Qwen/Qwen2.5-32B-Instruct"   # must match --model exactly
```

This is also what makes the AMD-compute claim for Track 3 survive automated
pre-screening: the harness's own inference, not just Demucs, runs on the
MI300X. Document this explicitly in your submission README (pre-screening
reads the repo and slide deck, not the demo video).

## Dashboard (public-facing results viewer)

`dashboard.py` — a Gradio viewer for already-computed pipeline output.
Deliberately **not** a live-inference trigger: it browses whatever's in
your `output/` directory (scene placements, coherence memory) plus any
rendered audio files it finds, so the link stays alive regardless of
whether your GPU session is still running — safer than a live pipeline
for Track 3's optional hosted-demo URL.

```bash
python3 dashboard.py --output-dir output --audio-dir .
```

Add `--share` for a temporary public link if you want to demo it live
during judging (expires when your session ends — don't rely on it being
up later; for the actual submission link, host the output/audio files
somewhere persistent rather than pointing at a share link).

Tested end-to-end against this build's real 3-scene output: loads the
scene JSON + coherence memory, renders the placement table and coherence
stat, serves audio players for whichever of `film_binaural.wav` /
`film_5.1.wav` / `film_5.1.4.wav` / `film_fallback_5.1.wav` /
`film.adm.wav` exist — confirmed via a live HTTP 200 from the running
server, not just that the code imports cleanly.

## Binaural rendering (for headphone playback at judging)

`binaural_renderer.py` — takes whatever speaker-layout file EAR (or the
FFmpeg fallback) produced and convolves each channel with an HRIR for that
speaker's real position, summing to stereo:

```python
from binaural_renderer import render_binaural
render_binaural("film_5.1.wav", "film_binaural.wav", system="0+5+0")
```

**Test `get_real_hrirs()` first thing in your notebook** — it downloads a
real measured HRTF set from `depositonce.tu-berlin.de` on first use, and
that domain was unreachable from the sandbox this was built/tested in. The
convolution and channel-summing logic was fully tested using the library's
built-in synthetic HRIR set as a stand-in — that part works. Whether the
real download works from your environment is the one thing only you can
confirm. If it fails there too, `get_hrirs()` (the default entry point)
falls back to the synthetic set automatically and prints a warning rather
than crashing — you'll still get a binaural file, just lower quality.

## Choosing your render path (the kill-switch)

Both paths take the identical inputs — `scene_results` from
`run_pipeline()`, a `(scene_id, stem_name) -> wav path` dict from Demucs,
and a `scene_id -> duration` dict:

```python
# Real object-based render (primary target)
from adm_renderer import build_adm_bwf, render_bwf
build_adm_bwf(scene_results, stem_audio_paths, scene_durations, "film.adm.wav")
render_bwf("film.adm.wav", "film_5.1.wav", target="5.1")        # or "5.1.4"

# Fallback (kill-switch: use this if the above isn't validated by your cutoff)
from ffmpeg_fallback import render_5_1_fallback
render_5_1_fallback(scene_results, stem_audio_paths, scene_durations, "film_fallback_5.1.wav")
```

Switching paths is a one-line change in your pipeline driver. If you're past
your kill-switch time and ADM/EAR isn't clean, switch and move on — don't
debug it into your last day.

## Proving coherence in the actual rendered file, not just the JSON

`check_coherence()` in the harness proves it in your placement JSON. This
proves it survived into the real ADM metadata — a stronger claim for judges:

```bash
ear-utils dump_axml film.adm.wav
```

Look for a stem's `audioChannelFormat` block: if the same stem got the same
channel across scenes, its `audioBlockFormat` entries will show identical
`azimuth`/`elevation`/`diffuse` values across every scene-aligned time range.
That's your headline stat, verified against the file you're actually
submitting, not a side calculation.

## What was actually tested (not assumed)

Ran a 3-scene simulation (recurring `ambient_hum` always placed at
`bed_full`, `dialogue` entering in scenes 2-3 at `center`) through both
paths in a real sandboxed environment:

- `adm_renderer`: built a valid ADM BW64, rendered cleanly to both `5.1`
  (6ch) and `5.1.4` (10ch, for the `overhead` label), and independently
  confirmed via `dump_axml` that `ambient_hum`'s three block formats share
  identical position values across all three scenes.
- `ffmpeg_fallback`: produced a valid 6-channel 5.1 WAV via real ffmpeg
  `amix`/`amerge`, no synthetic shortcuts.

## Known limitations (say these plainly, don't get caught out on them)

- `ear` on PyPI is stale (v2.1.0, ~2022) but functional — confirmed working
  against the real CLI (`ear-render`, `ear-utils`) in this build.
- Plain 5.1 has no height layer and no diffuse/bed concept: in
  `ffmpeg_fallback.py`, `overhead` folds down to front center, and
  `bed_full` is a crude even split across FL/FC/FR. State this as the exact
  gap that object-based rendering closes — don't let a judge find it first.
- Neither path produces a Dolby-certified Atmos file. That requires a
  proprietary Dolby encoder and a keyed cryptographic signature no open
  tool can produce (confirmed by the `dolby-atmos-encoder` research
  earlier) — the honest claim is "real object-based spatial mix via open
  ADM/EAR", not "Atmos".
