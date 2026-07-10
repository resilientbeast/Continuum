# SPEC — AI-Film Spatial Audio Coherence Agent

**Track:** AMD Developer Hackathon Act II — Track 3 (Unicorn / Open Innovation)
**Status as of this doc:** core pipeline components built and individually
tested; end-to-end run against real (non-synthetic) scene audio still
pending. See "Build status" below for the honest breakdown.

---

## 1. Problem statement

AI video generation (Veo, Runway, Kling) has outpaced AI-generated audio
spatiality. Generated films come out in flat stereo. No existing tool
reasons about spatial placement *across* a stitched, multi-scene film —
existing spatial-audio tools (upmixers, stem splitters) operate on a single
track in isolation. The gap isn't the upmixing itself (commodity tech) —
it's maintaining coherent placement for recurring elements (a character's
voice, an ambient bed, a musical motif) across cuts, the way a human sound
designer would.

**The novel contribution is the cross-scene coherence memory mechanism**,
not the placement reasoning or the rendering — both of those lean on
existing tools (an LLM, Demucs, EAR). This is a sequential per-scene
pipeline with JSON memory carried forward, not a ReAct/tool-loop agent —
frame it that way to judges; don't overclaim agentic architecture the
system doesn't have.

---

## 2. Architecture

```
input clips → scene segmentation → per-scene Demucs stem separation
     → stem feature extraction (energy / transients / brightness)
     → placement-reasoning LLM agent (self-hosted on MI300X via vLLM),
       reads + writes a persistent coherence-memory JSON across scenes
     → render:
         PRIMARY: ADM metadata generation → EBU EAR render (real
                  object-based mix, BS.2051 speaker layout)
         FALLBACK (kill-switch): FFmpeg channel-based 5.1 mixdown
     → output: rendered multichannel file + scene-by-scene rationale
       report + quantified coherence stat, for the judge-facing writeup
```

### Why self-hosted vLLM, specifically

Track 3's automated pre-screening **disqualifies submissions that don't
demonstrate AMD compute usage**, and pre-screening only reads the GitHub
repo, slide deck, and live demo/hosted URL — **not the demo video**. Demucs
alone doesn't meaningfully stress an MI300X (it needs ~3–7GB VRAM against
192GB available). Self-hosting the placement-reasoning LLM via vLLM is what
makes the AMD-compute claim genuine and — more importantly — *documented in
the repo itself*, not just true in spirit.

---

## 3. Components

### 3.1 Scene segmentation
PySceneDetect, automatic shot-detection. Not yet load-bearing-tested in this
build; low technical risk, high time-cost risk if it needs tuning against
real AI-generated footage. If it stalls, hardcoding scene boundaries by
timestamp for the demo clip is an acceptable substitute — the coherence
mechanism doesn't depend on segmentation being automatic, only on scene
boundaries existing.

### 3.2 Stem separation
Demucs (`facebookresearch/demucs` is archived — **pin the maintained
`adefossez/demucs` fork**). Runs on PyTorch/ROCm unchanged —
`torch.cuda.is_available()` returns `True` under ROCm without code changes,
confirmed against AMD's own docs.

### 3.3 Feature extraction — `stem_feature_extractor.py`
RMS energy (bucketed low/medium/high), onset-based transient detection,
silence ratio, spectral-centroid brightness proxy. Pure librosa/numpy, no
GPU dependency. **Tested** as a standalone module in earlier review; not
yet re-run against this build's exact harness output shape.

### 3.4 Placement-reasoning agent — `placement_agent_harness.py`
Scene-by-scene LLM call. Loads/saves a JSON coherence-memory file across
scenes; system prompt instructs the model to reuse a recurring element's
established channel placement unless visual context justifies a change.

**Changes made in this build:**
- Defaults to a self-hosted vLLM endpoint (`LLM_BASE_URL`,
  `LLM_API_KEY`, `LLM_MODEL` env vars — OpenAI-compatible, no code change
  needed to point elsewhere).
- Added retry/backoff (3 attempts) on connection errors and malformed JSON —
  the original had no retry, so one bad response killed the whole run.
- Defensive JSON extraction (strips markdown fences) since smaller
  self-hosted instruct models are more likely than `gpt-4o` to wrap output
  in fences despite `response_format={"type":"json_object"}` and explicit
  instructions.

**Model recommendation:** mid-size instruct model (e.g.
`Qwen/Qwen2.5-32B-Instruct`), not the originally-scoped 70B-class — given
the compressed timeline, download/load time on a 70B is a real risk, and a
32B model is still a legitimate, defensible self-hosted-on-MI300X claim.

**Valid channel vocabulary:** `center`, `left`, `right`, `surround_left`,
`surround_right`, `bed_full`, `overhead`.

**Not yet tested:** a real run against the vLLM server (this build tested
the ADM/render layer standalone with simulated harness output; the harness
itself against a live vLLM endpoint is the next thing to verify).

### 3.5 Coherence memory
`check_coherence()` in the harness diffs channel assignments for recurring
stem names across scenes and produces the headline stat (e.g. "6/6 scenes
correctly reused placement"). **This must survive every scope cut** — if
forced to drop something under time pressure, drop the real ADM/EAR render
before dropping this.

### 3.6 ADM generation + EAR render — `adm_renderer.py` (PRIMARY render path)

Builds a real ADM BW64 file (ITU-R BS.2076 metadata + audio) and renders it
via the actual EBU EAR reference renderer (`ear-render`, BS.2127).

**Key design decision:** one continuous ADM Object track per *recurring
stem name* (not one track per scene-stem pair). This means when the
coherence memory keeps reusing a placement, that reuse is directly visible
as **identical azimuth/elevation/diffuse values across multiple
`audioBlockFormat` entries in the actual ADM XML** — a stronger, independently
verifiable coherence claim than a JSON diff, because it's checkable in the
file you're actually submitting.

**Channel → BS.2127 position mapping** (confirmed against EAR's own
`2051_layouts.yaml`, not assumed):

| Channel label | Azimuth | Elevation | Diffuse | Notes |
|---|---|---|---|---|
| `center` | 0.0 | 0.0 | 0.0 | |
| `left` | 30.0 | 0.0 | 0.0 | matches M+030 |
| `right` | -30.0 | 0.0 | 0.0 | matches M-030 |
| `surround_left` | 110.0 | 0.0 | 0.0 | matches M+110 |
| `surround_right` | -110.0 | 0.0 | 0.0 | matches M-110 |
| `overhead` | 0.0 | 90.0 | 0.0 | needs a height-layer target system |
| `bed_full` | 0.0 | 0.0 | 1.0 | uses ADM's native `diffuse` param instead of picking an arbitrary direction for something meant to feel like "everywhere" |

**Target render systems** (real BS.2051 systems `ear-render` supports):
`5.1` → `0+5+0` (de-risked baseline, no height); `5.1.4` → `4+5+0` (adds 4
height speakers, needed for `overhead` to mean anything).

**Verification command** (for the submission writeup — proves coherence in
the actual file, not a side calculation):
```bash
ear-utils dump_axml film.adm.wav
```

### 3.7 FFmpeg 5.1 fallback — `ffmpeg_fallback.py` (KILL-SWITCH path)

Same input shape as `adm_renderer.build_adm_bwf` — identical
`scene_results` / `stem_audio_paths` / `scene_durations` — so switching
paths is a one-line change in the pipeline driver, not a rewrite. Uses real
ffmpeg `amix`/`amerge`, not a simplified stand-in.

**Explicit, stated-up-front limitations** (say these before a judge finds
them): plain 5.1 has no height layer and no diffuse/bed concept, so
`overhead` folds down to front center, and `bed_full` is a crude even split
across FL/FC/FR at reduced gain.

---

### 3.8 Orchestrator — `main.py`

Ties all stages together: segmentation → per-scene Demucs separation →
feature extraction → placement agent → render (with the ADM/EAR-then-
FFmpeg kill-switch built in as actual try/except code, not just a manual
decision) → binaural. Each stage writes its own output file, so
`--only segment,separate` lets you resume from any point instead of
redoing everything after a later-stage failure.

Tested end-to-end via real orchestrator function calls: real scene
segmentation on a real video, real feature extraction on real audio, the
real agent against a mock server, the real render kill-switch (ADM/EAR
path, with the fallback wiring in place though not forced to trigger),
and the real binaural stage. **One bug this testing caught and fixed:**
the binaural stage was passing the friendly target label ("5.1") straight
through where the binaural renderer expected the actual BS.2051 system
string ("0+5+0") — would have crashed on first real use had this not been
run.

**Only stage not executable in this build's sandbox:** real Demucs
separation (`stage_separate`). Installing `demucs` pulled its full CUDA
torch dependency stack and exhausted the sandbox's disk quota mid-install,
leaving `torch` broken — a sandbox limitation (small disk, no real GPU),
not a code issue. The Demucs CLI invocation and output-path convention in
`stage_separate` match documented `adefossez/demucs` usage, but this is
the one piece written from documentation rather than an observed run. Test
it first and in isolation: `python3 main.py --input-video clip.mp4 --only segment,separate`.

**Dependency note found during this testing:** `ear` imports the
deprecated `pkg_resources`, which setuptools 81+ removes entirely. If you
hit `ModuleNotFoundError: No module named 'pkg_resources'`, run
`pip install "setuptools<81"`.

## 4. AMD / ROCm setup corrections

The original Dockerfile had two real bugs, now fixed:

1. **`HSA_OVERRIDE_GFX_VERSION=9.4.2` — removed.** This variable exists to
   spoof an *unsupported* consumer GPU as a supported ISA (e.g. gfx1030).
   MI300X is `gfx942`, a first-class officially-supported ROCm/CDNA3
   target — setting this override on already-supported hardware can
   misroute kernels (`hipErrorNoBinaryForGPU`) or cause performance
   regressions. It was solving a problem that doesn't exist on this GPU.

2. **`PYTORCH_ROCM_ARCH=gfx942` — removed.** This is a build-from-source
   compiler flag; it has no effect on the prebuilt pip wheels this
   Dockerfile installs. Cargo-cult, not functional.

3. **Torch-install-order bug — fixed.** The original installed `demucs`
   before the ROCm-specific torch build. `pip install demucs` pulls a
   generic PyPI torch first; installing ROCm torch afterward risks pip
   seeing torch as "already satisfied" and silently skipping the ROCm
   build — `torch.cuda.is_available()` would then return `False` with no
   error raised anywhere. Fixed by installing ROCm torch first, then
   `demucs` with `--no-deps`.

**Docker flags confirmed correct** (matches AMD's documented invocation
exactly): `--device=/dev/kfd --device=/dev/dri --group-add video
--ipc=host --shm-size 8G`.

**Note on the AMD Developer Cloud notebook environment:** the managed
notebook images come with ROCm 7.2 + vLLM 0.16.0 + PyTorch 2.9 pre-baked,
which sidesteps the install-order issue entirely for actual development —
the Dockerfile above matters for repo reproducibility/judge inspection, not
as the environment you're iterating in day-to-day.

---

## 5. Corrected claims (things the original spec got wrong — don't repeat)

These were run down explicitly so the submission doesn't repeat them:

- **"Atmos-compatible" is not an honest claim.** Neither EAR nor Cavern can
  produce a Dolby-certified Atmos deliverable. True Atmos requires DAMF or
  an encoded DD+ JOC / AC-4 stream, which needs Dolby's proprietary
  encoder. A from-scratch open-source encoder project
  (`raress96/dolby-atmos-encoder`) got provably correct object metadata
  past both ffmpeg and Cavern as validators and *still* hit a hard wall:
  the `emdf_protection` field is a keyed cryptographic MAC, not a
  computable checksum — brute-forcing all 256 CRC-8 polynomial variants
  against real Dolby frames found zero matches. **The honest claim is
  "real object-based spatial mix via open ADM rendering (BS.2051
  layouts)," not "Atmos."**
- **ADM is not a streaming delivery format.** ADM BWF is a
  production/mastering/interchange format (ITU-R BS.2076, genuinely open
  and codec-agnostic). Streaming platforms ingest DD+ JOC or AC-4 for
  playback, not raw ADM BWF. Don't claim platform delivery-format
  acceptance.
- **EAR has no binaural output.** It renders to BS.2051 speaker layouts
  only. If judges listen on headphones, that's a separate rendering stage
  this build does not yet include (see Section 7, cut items).
- **Cavern is C#/.NET, not Python**, and its license discourages commercial
  use. Not used in this build for exactly that reason — cross-language
  integration cost plus a non-permissive license for a hackathon
  submission wasn't worth it.
- **MI300X is not the bottleneck for Demucs** (~3–7GB VRAM against
  192GB available) — the actual justification for the hardware is
  self-hosting the LLM agent, not stem separation. Say this explicitly
  rather than let "we used an MI300X" imply the GPU was doing something it
  wasn't.

---

## 6. Build status (honest breakdown)

**Built and independently tested against real synthetic audio in a
sandboxed run** (3-scene simulation: a recurring `ambient_hum` stem always
placed at `bed_full`, `dialogue` entering in scenes 2–3 at `center`):
- `adm_renderer.py` — valid ADM BW64 built; rendered cleanly to both `5.1`
  (6ch) and `5.1.4` (10ch); `dump_axml` confirmed identical position values
  across `ambient_hum`'s three scene-aligned blocks.
- `ffmpeg_fallback.py` — valid 6-channel 5.1 WAV via real ffmpeg
  `amix`/`amerge`.
- Dockerfile — corrected, not yet rebuilt/run in CI.

**Also tested** (against a local mock OpenAI-compatible server standing in
for vLLM, since this build has no GPU access — real request/response shape,
not a unit-test stub): `placement_agent_harness.py` end-to-end across 3
scenes, with the mock server deliberately forced to return malformed,
fenced JSON on scene 2's first attempt. Confirmed output:
```
Scene 1: 1 placements logged
Scene 2: attempt 1/3 - model returned invalid JSON: Expecting property name enclosed in double quotes...
Scene 2: 2 placements logged
Scene 3: 2 placements logged
--- coherence check ---
{'matches': 3, 'total_recurring_checks': 3}
```
The retry/fence-stripping path genuinely fires and recovers — this isn't
inferred from reading the code, it's an observed run.

**Also verified via the orchestrator (`main.py`) directly, not just each
module in isolation:** real scene segmentation on a real test video → real
feature extraction on real audio → real agent call (mock server) → real
ADM/EAR render → real binaural render, chained exactly as the orchestrator
wires them. This caught a real bug — the binaural stage was passing the
friendly target label ("5.1") straight through where the binaural renderer
expected the actual BS.2051 system string ("0+5+0") — before it could
surface on a real run. See Section 3.8.

**Not yet tested:**
- The harness against a *real* model's output (mock server returns
  scripted responses; a real vLLM-served model's actual JSON-following
  behavior — especially a smaller model's tendency to hallucinate channel
  names or add commentary — is still unverified).
- Real Demucs separation (`main.py`'s `stage_separate`) — installing
  Demucs exhausted this build's sandbox disk quota pulling its full CUDA
  torch stack; the CLI invocation matches documented usage but wasn't
  observed running. Test this stage first and in isolation.
- The full pipeline against real Demucs-separated stems (all render-layer
  testing so far used synthetic sine-tone stems — sufficient to prove the
  ADM/coherence mechanics, not sufficient to prove the audio sounds right).
- PySceneDetect against actual AI-generated footage.

---

## 7. Remaining plan, given the compressed timeline

Given the actual credit-activation delay, effective build time is closer to
2 days than the original 5. Priority order, most important first:

1. Get vLLM serving a chosen model on the MI300X notebook; point the
   harness at it; run one real scene end-to-end.
2. Run a real 3–4 scene test clip through the full spine (segmentation →
   Demucs → features → agent → memory) and confirm coherence holds.
3. **Kill-switch checkpoint:** attempt `adm_renderer.py` against real
   pipeline output. Set a hard cutoff time. If not clean by then, switch to
   `ffmpeg_fallback.py` and move on — do not let this bleed into the last
   day.
4. Package before/after audio, the quantified coherence stat (from both
   `check_coherence()` and `dump_axml` if the ADM path made it), README,
   and slide deck — with AMD/vLLM usage explicit and early in both, since
   pre-screening reads those, not the demo video.
5. Submit with buffer before the deadline.

**Cut if time runs out, in this order:** binaural/SOFA rendering stage
(never started — see below) → real ADM/EAR render (falls back to FFmpeg,
already built and tested) → automatic scene segmentation (falls back to
hardcoded timestamps). **Never cut:** coherence memory itself.

**Binaural rendering for headphone playback** — `binaural_renderer.py`.
Convolves each EAR-rendered speaker channel with an HRIR at that speaker's
real BS.2051 position and sums to stereo, since judges will very likely
listen on headphones and EAR's own output is speaker-layout PCM, not
binaural. Uses `spaudiopy` rather than `libspatialaudio` (C#/.NET,
originally scoped) — pure Python, no cross-language integration cost.

Tested against the real 5.1 and 5.1.4 EAR output from Section 6, using
`spaudiopy`'s built-in synthetic HRIR set (confirmed correct convention: a
+30° / left-labeled source produces measurably higher left-ear than
right-ear HRIR energy). Both produced valid stereo files. **One dependency
not verified end-to-end:** the real measured HRTF set
(`get_real_hrirs()`) downloads from `depositonce.tu-berlin.de` at runtime,
which was unreachable from this build's sandboxed network — test that one
call first in your notebook. It falls back to the synthetic set
automatically on failure, so a blocked download degrades quality rather
than breaking the render.

---

## 8. Track 3 submission checklist

Per the Participant Guide:
- [ ] GitHub repository URL (public) — **must** contain: this pipeline
      code, the corrected Dockerfile, and a README stating AMD/MI300X/vLLM
      usage explicitly (pre-screening reads this, not the video)
- [ ] Slide deck (PDF) — same AMD-usage requirement applies
- [ ] Demo video
- [ ] Live demo / hosted URL — optional but recommended
- No Docker image submission required for Track 3 (unlike Tracks 1/2)
- Automated pre-screening checks AMD resource usage + originality before
  human judging — **disqualification risk if AMD compute usage isn't
  demonstrated**, so don't leave this implicit
