# Continuum Landing Page — Comprehensive Revamp Prompt

Paste this to your coding agent (working against the Continuum repo / Vercel deploy at continuum-xi-ashen.vercel.app).

---

## Context

Continuum is a pipeline that generates cross-scene spatially coherent audio for AI-generated film. The actual implemented stack is:

- Scene segmentation (PySceneDetect)
- Stem separation (Demucs)
- Placement reasoning agent powered by Fireworks-hosted models (Gemma for reasoning, a vision-language model for scene captioning)
- A **cross-scene coherence memory** — a persisted JSON state that recurring audio elements (ambient beds, character dialogue, musical motifs) get checked against, so they keep a consistent spatial position across cuts instead of being placed independently per scene
- Render output is selectable at export time across **four formats**: Stereo Binaural (HRTF convolution via spaudiopy, for headphones), 5.1 Surround, 5.1.4 Immersive, and 7.1.4 Immersive. The immersive/height formats are real object-based renders to BS.2051 speaker layouts via ADM metadata piped through the open-source EBU EAR reference renderer — this is a working multi-format spatial render pipeline already live in the dashboard, not a stereo-only tool with a single surround fallback

**The core novel contribution is the coherence memory mechanism.** Stem separation, placement reasoning, and rendering are each built on established/commodity techniques — the thing nobody else in this space is doing is making spatial placement decisions *persist and get reused* across scene cuts.

Audience: this page will be seen by hackathon judges (lablab.ai AMD Developer Hackathon Act II, Track 3) evaluating the project alongside the GitHub repo and slide deck, as well as general visitors.

## What's wrong with the current page

Looking at the live site today:

1. **The actual differentiator is completely absent.** The hero and the three feature cards ("Intelligent Stem Separation," "Context-Aware Placement," "5.1 Binaural Render") describe a generic AI audio upmixer. Nothing on the page explains or shows cross-scene coherence memory — the one thing that makes this project different from any other AI stem-separation-and-pan tool. A judge could read the entire page and never learn what's novel here.
2. **A technical claim is inaccurate and undersells the actual product.** The "5.1 Binaural Render" card describes exporting "a cinematic 5.1 surround mix folded down to binaural stereo" — this conflates two separate render paths into one sentence that isn't how the pipeline works, and it hides that the dashboard already offers four selectable output formats (Stereo Binaural, 5.1 Surround, 5.1.4 Immersive, 7.1.4 Immersive), including real object-based immersive/height renders. The landing page is currently underselling a capability that's already built and live.
3. **No proof, no architecture, no repo link.** There's a "View Architecture" button with an unclear destination, no quantified evidence of the coherence claim, and no link to the GitHub repo anywhere on the page.
4. **The page is shallow.** Hero + one three-card section + footer. There's no room to actually explain the pipeline or make the case for why this matters.

## Goal

Rebuild the page so that:

1. Cross-scene coherence memory is the headline story — not buried, not omitted.
2. Every technical claim is verified against what's actually implemented before it goes on the page.
3. It reads credibly to a technical judge while staying accessible to a general visitor.
4. The existing dark/violet-gradient visual identity is kept, but the page gains the depth of sections it needs to actually explain the product.

## Guardrails — do not violate these

- **Never claim Dolby Atmos support, compatibility, or certification anywhere.** The accurate claim is "open, object-based spatial rendering via ADM and the EBU EAR reference renderer," with FFmpeg 5.1 as a channel-based fallback. Dolby Atmos requires a proprietary licensed encoder this project does not have or claim to have.
- **Never describe 5.1 and binaural as the same output.** They are two distinct render paths (object-based/channel-based render vs. HRTF binaural render for headphones). Say so explicitly wherever render outputs are described.
- **Never mention vLLM, self-hosted inference, or AMD GPUs as the current inference backend in marketing copy.** Inference is Fireworks-hosted (already correctly stated as "Powered by Fireworks AI & Gemma" — keep that framing). If AMD is referenced at all, it should only be as hackathon-platform context (e.g. a small badge), never as the current inference method.
- **Every CTA must route somewhere real.** Before changing anything, check what "Start Mastering Free," "Get Started," "Sign In," and "View Architecture" currently do. Fix or repoint dead/misleading links. Don't let marketing promise a capability that isn't live yet.

## Task list

0. **Audit first.** Read the current landing page component(s) and copy, and cross-reference every factual claim against the actual README and pipeline code before writing anything new. If you find a discrepancy between existing copy and what the code actually does, flag it rather than silently guessing which one is right.
1. **Rewrite the hero.** Headline and subhead should foreground cross-scene spatial continuity/coherence as the core value proposition, not generic "AI mastering." Keep the punch, but make the actual mechanism legible in the first screen.
2. **Add a "how it works" pipeline section** walking through the real stages: scene segmentation → stem separation → visual context captioning → placement reasoning → coherence memory check → spatial render. Keep it visual, not a wall of text.
3. **Add a dedicated coherence memory showcase section — this is the centerpiece of the page.** Show, don't just tell: something like a simple before/after or timeline visual — e.g. "Scene 1: ambient hum → surround-left" ... "Scene 6: ambient hum → surround-left (memory match)" — contrasted with what happens without memory (placements drift/jump scene to scene). Should be understandable at a glance to someone with no audio background.
4. **Add a quantified-proof section**, modeled on the project's own coherence-checking logic (e.g. "N/N recurring elements correctly retained placement across cuts"). Use a real number pulled from an actual pipeline run if one is available; otherwise use a clearly marked placeholder rather than inventing a number.
5. **Rework the three feature cards** to be technically accurate and reordered so coherence memory is first/most prominent — not the thing left out entirely.
6. **Fix the render-output copy.** Represent all four real, selectable output formats accurately: Stereo Binaural (HRTF convolution, headphones), 5.1 Surround, 5.1.4 Immersive, and 7.1.4 Immersive (object-based ADM/EBU EAR renders to BS.2051 speaker layouts). Don't collapse these into one vague "5.1 binaural" claim — the format selector already live in the dashboard is a genuine selling point and should be shown, not simplified away.
7. **Add a market-positioning section**: AI video tools (Veo, Runway, Kling, etc.) generate great visuals but flat stereo/mono audio with no cross-clip continuity; Continuum is the missing spatial-continuity layer for that stack.
8. **Fix the "View Architecture" button** — either link it to a real architecture diagram/section on the page, or repoint it to the GitHub repo.
9. **Add a GitHub repo link** somewhere persistent (nav or footer).
10. **Verify every CTA destination** matches the actual current app state.
11. **Responsive and accessibility pass** — mobile layout, color contrast, alt text on any new diagrams.
12. **Final QA pass**: read the whole page as a skeptical hackathon judge would, and flag any remaining vague or unsubstantiated claim before calling it done.

## Tone

Direct and technically confident, not hypey. The confidence should come from specificity — naming the real pipeline stages, the real mechanism, honest scoping — rather than superlatives like "revolutionary" or "flawless." Keep some marketing energy in the hero, but everything below the fold should read like it was written by the person who actually built the coherence-memory mechanism, not generic SaaS template copy.

## Deliverable

Updated landing page, plus a short summary of: (a) what copy/sections changed and why, (b) any discrepancies found between old copy and repo reality, (c) any TODOs left for a real coherence metric, demo assets, or architecture diagram that still need to be filled in.
