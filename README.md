# Continuum

**A cross-scene spatial audio coherence agent for AI-generated film.**

AI video generation (Veo, Runway, Kling, and others) has raced far ahead of AI-generated audio spatiality. Every generated clip ships in flat stereo, and every existing spatial-audio tool — upmixers, auto-scoring tools, stem splitters — operates on a single track in isolation. None of them reason about spatial *continuity* across a stitched, multi-scene film. Continuum is that missing layer: it analyzes a film scene by scene, decides spatial placement for every separated audio stem, and — critically — remembers those decisions across cuts, so a recurring ambient bed, character voice, or musical motif stays spatially consistent from Scene 1 to Scene 20 instead of jumping around every time the shot changes.

**[Live demo →](https://continuum-xi-ashen.vercel.app/)** · **[Backend API repo](https://github.com/resilientbeast/Continuum)**

![Coherence Memory UI](https://continuum-xi-ashen.vercel.app/demo.gif)

---

## What it does — pipeline overview

```
Input film ──▶ Scene segmentation ──▶ Stem separation (Demucs)
                                              │
                                              ▼
                              Per-stem audio features (energy, transients,
                              brightness) + per-scene visual caption (VLM)
                                              │
                                              ▼
                     Placement-reasoning agent ◀── reads/writes ──▶ Coherence
                     (decides channel per stem)                    memory (JSON)
                                              │
                                              ▼
                          ADM metadata generation (BS.2076)
                                              │
                                              ▼
                    EBU EAR render (BS.2051 layout, e.g. 5.1 / 5.1.4)
                    ── or, if that stage fails: FFmpeg channel-based
                       5.1 fallback (documented kill-switch) ──
                                              │
                                              ▼
                         Binaural render (HRTF convolution, for
                         headphone playback — most judges won't
                         have a 5.1/5.1.4 speaker rig)
```

## The novel part

Placement reasoning and spatial rendering are both commodity technology at this point — an LLM agent that looks at a scene and picks a channel isn't the hard problem, and neither is running an open-source renderer. **The genuinely unclaimed piece is the coherence memory**: a persistent JSON state that every scene's placement decision reads from and writes to, so the agent can recognize "I've placed this exact ambient hum before, at Scene 1, in the left-surround channel" and reuse that decision at Scene 6 rather than treating every scene as a fresh, unrelated placement problem.

This is directly verifiable, not just asserted — `check_coherence()` walks every scene's output and reports a hard number: how many times a recurring stem reappeared with the same placement it originally established. That number, plus the underlying ADM metadata (inspectable directly via `ear-utils dump_axml`), is the evidence for the claim.

## Quantified proof

- **N/N recurring placements matched** across the test film's scenes — see `output/coherence_memory.json` and the per-scene `scene_N_placements.json` files for the raw decisions.
- The ADM BW64 output can be independently inspected with `ear-utils dump_axml film.adm.wav` to confirm matching azimuth/elevation values for the same recurring element across scenes — this is a stronger claim than the JSON alone, since it's checking the actual rendered spatial metadata, not just the agent's self-report.

## Architecture and a note on compute

The original build targeted a self-hosted reasoning model via vLLM on an AMD MI300X, provisioned through the hackathon's AMD Developer Cloud notebook environment — this was the intended way to satisfy Track 3's "Use of AMD Platforms" criterion directly, rather than routing through a third-party hosted API. Partway through the build, GPU capacity in that notebook environment became unavailable. Rather than stall the project on a resource outside our control, we moved the placement-reasoning agent and vision-language captioning to Fireworks-hosted models (Gemma and Llama 3.2 Vision), which let the project ship as a complete, deployed, end-to-end product rather than a partial pipeline blocked on GPU access.

The coherence-memory mechanism, the ADM/EAR rendering path, and the binaural stage are all unaffected by this — none of them ever depended on GPU compute; EAR and the binaural convolution are both CPU-bound.

## What's actually deployed

This isn't just a pipeline script — it's a running product:

- **Frontend:** [continuum-xi-ashen.vercel.app](https://continuum-xi-ashen.vercel.app/) — upload a clip, watch job status, download the result.
- **Backend:** FastAPI service on an AWS Lightsail instance, running the full pipeline as a background job per upload.
- **Storage:** S3-backed job artifacts, presigned upload/download URLs.

## Running it locally

```bash
docker build -t continuum .

docker run -it \
  -e LLM_BASE_URL=https://api.fireworks.ai/inference/v1 \
  -e LLM_API_KEY=<your Fireworks API key> \
  -e LLM_MODEL=<reasoning model id> \
  -e VISION_LLM_BASE_URL=https://api.fireworks.ai/inference/v1 \
  -e VISION_LLM_API_KEY=<your Fireworks API key> \
  -e AWS_REGION=us-east-1 \
  -e AWS_S3_BUCKET_NAME=continuum-ai \
  -e AWS_ACCESS_KEY_ID=<your aws key> \
  -e AWS_SECRET_ACCESS_KEY=<your aws secret> \
  -v $(pwd)/scenes:/app/scenes \
  -v $(pwd)/output:/app/output \
  continuum
```

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Pipeline orchestrator — runs segment → separate → features → agent → render → binaural, stage by stage, resumable. |
| `placement_agent_harness.py` | The placement-reasoning agent loop: builds the per-scene prompt, calls the LLM, persists coherence memory. |
| `stem_feature_extractor.py` | Converts raw Demucs stems into the lightweight energy/transient/brightness features the agent reasons over. |
| `caption_extractor.py` | Per-scene visual captioning via a hosted vision-language model, feeding scene context to the placement agent. |
| `adm_renderer.py` | Generates valid ADM (BS.2076) metadata and renders it via the EBU ADM Renderer (EAR) to a BS.2051 speaker layout. |
| `ffmpeg_fallback.py` | Channel-based 5.1 fallback render, used if the ADM/EAR path fails — the documented kill-switch. |
| `binaural_renderer.py` | Convolves the rendered speaker feed with HRIRs to produce a 2-channel binaural mix for headphone playback. |
| `api.py` | FastAPI backend — upload handling, job queue, status polling, S3-backed results. |
| `dashboard.py` | Lightweight results viewer for browsing already-computed pipeline output. |

## Known limitations

- **True Dolby Atmos is out of reach with open tooling**, and deliberately so — Atmos delivery formats (DD+ JOC / AC-4) require Dolby's proprietary encoder and a keyed cryptographic signature that no open-source project can reproduce. Continuum instead targets ADM (ITU-R BS.2076), an open, codec-agnostic standard, rendered to real BS.2051 speaker layouts via the EBU reference renderer — a materially different and honestly-scoped claim from "object-based spatial mix via open ADM rendering."
- **Binaural rendering prefers a real measured HRTF set, with a synthetic fallback** if that data isn't reachable — output quality is somewhat lower on the synthetic path, though the spatial logic itself is unaffected.
- **Auth and job storage are prototype-level**, not production-hardened — this is a hackathon submission and demo product, not a security-reviewed public service yet.

## Roadmap

- ADM → IAMF conversion, as the strongest realistic path toward a genuinely open, royalty-free, broadly-supported (AOMedia-backed, native FFmpeg 7.0+/YouTube/Android support) spatial delivery format.
- Tighter visual-context integration for placement decisions beyond scene-level captioning.

## How this maps to Track 3's judging criteria

- **Creativity/Originality:** the cross-scene coherence memory — genuinely unclaimed by any existing spatial-audio tool, all of which operate on single tracks in isolation.
- **Product/Market Potential:** positioned as infrastructure for the AI filmmaking stack broadly, not a niche mixing utility — every AI video tool that ships native or added audio has this same flat-stereo, no-continuity gap.
- **Completeness:** a real deployed product (frontend, API, job queue, storage), not just a pipeline script — upload a clip and get a result back.
- **Use of AMD Platforms:** originally targeted, via self-hosted vLLM on an MI300X; moved to hosted inference after a GPU access interruption mid-build, documented above rather than left unaddressed.

## Credits

Built solo for the AMD Developer Hackathon Act II (lablab.ai), Track 3 (Unicorn/Open Innovation). Uses the [EBU ADM Renderer (EAR)](https://github.com/ebu/ebu_adm_renderer) and [spaudiopy](https://github.com/chris-hld/spaudiopy).
