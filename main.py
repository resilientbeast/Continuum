"""
End-to-end pipeline orchestrator.

    python3 main.py --input-video clip.mp4 --output-dir output

Stages, in order, each resumable independently (writes its own output so a
failure downstream doesn't force redoing everything upstream):

  1. Scene segmentation (PySceneDetect)              - TESTED in this build
  2. Per-scene audio extraction + Demucs separation   - NOT TESTED here (see note)
  3. Feature extraction (stem_feature_extractor.py) +
     automatic visual captioning (caption_extractor.py)
  4. Placement-reasoning agent (placement_agent_harness.py) - tested against
     a mock server; point at your real vLLM endpoint via the usual env vars
  5. Render, with kill-switch: ADM+EAR primary, FFmpeg fallback on any
     failure                                          - both paths TESTED
  6. Binaural stereo render for headphones            - TESTED (synthetic
     HRIR fallback path; real HRTF download untested here, see
     binaural_renderer.py's own note)
  7. Optional: launch the results dashboard

*** Stage 2 (Demucs) was NOT executable in this build's sandbox: it pulled
Demucs' full CUDA torch dependency stack, exhausted the sandbox's disk
quota mid-install, and left torch in a broken state. That's a sandbox
limitation (small disk, no real GPU) - your notebook has both a real
MI300X and normal disk space. Run this stage first and in isolation
(`python3 main.py --input-video clip.mp4 --only segment,separate`) before
trusting the rest of the run, since it's the one piece here written from
documented Demucs CLI usage rather than an observed successful run. ***

*** Stage 3's visual captioning requires a second self-hosted vLLM instance
serving a vision-capable model (e.g. Qwen2.5-VL-7B-Instruct) on its own
port, in addition to the reasoning model. See caption_extractor.py for the
VISION_LLM_* env vars. If that server isn't up, captioning fails per-scene
and visual_caption falls back to null for that scene rather than aborting
the run -- the agent is instructed to reason from stems alone when that
happens. ***
"""

import argparse
import json
import subprocess
import sys
import traceback
from pathlib import Path

from scenedetect import detect, ContentDetector

from stem_feature_extractor import extract_stem_features
from caption_extractor import extract_keyframe, caption_scene
from placement_agent_harness import run_pipeline, check_coherence
from adm_renderer import build_adm_bwf, render_bwf, check_adm_coherence
from ffmpeg_fallback import render_5_1_fallback
from binaural_renderer import render_binaural, get_hrirs

DEMUCS_MODEL = "htdemucs"  # 4 stems: vocals, drums, bass, other
STAGE_ORDER = ["segment", "separate", "features", "agent", "render", "binaural", "dashboard"]


def stage_segment(video_path, output_dir):
    """Detects scenes and writes their boundaries. TESTED: confirmed
    against a synthetic 3-scene (2s/1.5s/2.5s hard-cut) test video, found
    boundaries at 2.00s/3.52s/6.04s - within encoding rounding of exact."""
    scene_list = detect(str(video_path), ContentDetector())
    scenes = []
    for i, (start, end) in enumerate(scene_list, start=1):
        scenes.append({
            "scene_id": i,
            "start": start.get_seconds(),
            "end": end.get_seconds(),
            "duration": end.get_seconds() - start.get_seconds(),
        })
    if not scenes:
        # ContentDetector found no cuts at all - treat the whole clip as
        # one scene rather than failing the pipeline outright.
        import subprocess as sp
        probe = sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
                       capture_output=True, text=True, check=True)
        duration = float(probe.stdout.strip())
        scenes = [{"scene_id": 1, "start": 0.0, "end": duration, "duration": duration}]

    out_path = Path(output_dir) / "scenes.json"
    out_path.write_text(json.dumps(scenes, indent=2))
    return scenes


def stage_separate(video_path, scenes, output_dir):
    """
    Extracts each scene's audio, runs real Demucs on it (4-stem: vocals,
    drums, bass, other), returns {(scene_id, stem_name): wav_path}.

    NOT TESTED end-to-end in this build - see the module docstring. The
    demucs CLI invocation and output path convention below match Demucs'
    documented usage (output goes to <out>/<model_name>/<track_stem>/*.wav)
    as of the maintained adefossez/demucs fork - verify this against
    whatever version actually installs in your notebook.
    """
    output_dir = Path(output_dir)
    scene_audio_dir = output_dir / "scene_audio"
    demucs_out_dir = output_dir / "demucs"
    scene_audio_dir.mkdir(parents=True, exist_ok=True)
    demucs_out_dir.mkdir(parents=True, exist_ok=True)

    stem_audio_paths = {}
    for scene in scenes:
        sid = scene["scene_id"]
        scene_wav = scene_audio_dir / f"scene_{sid}.wav"

        subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path),
            "-ss", str(scene["start"]), "-to", str(scene["end"]),
            "-vn", "-acodec", "pcm_s16le", "-ar", "48000",
            str(scene_wav),
        ], check=True, capture_output=True, text=True)

        subprocess.run([
            "demucs", "-n", DEMUCS_MODEL, "-o", str(demucs_out_dir), str(scene_wav),
        ], check=True, capture_output=True, text=True)

        track_name = scene_wav.stem  # e.g. "scene_1"
        stem_dir = demucs_out_dir / DEMUCS_MODEL / track_name
        for stem_name in ["vocals", "drums", "bass", "other"]:
            stem_path = stem_dir / f"{stem_name}.wav"
            if stem_path.exists():
                stem_audio_paths[(sid, stem_name)] = stem_path

    manifest = {f"{sid}:{name}": str(p) for (sid, name), p in stem_audio_paths.items()}
    (output_dir / "stem_manifest.json").write_text(json.dumps(manifest, indent=2))
    return stem_audio_paths


def stage_features(video_path, scenes, stem_audio_paths, output_dir):
    """
    Builds the harness's `stems` input per scene (TESTED: this build's
    stem_feature_extractor.py run against real synthetic stem files), and
    now also generates visual_caption automatically: a keyframe is pulled
    directly from the original video at each scene's midpoint timestamp
    and captioned via a self-hosted vision-language model.

    Captioning failure for a given scene is non-fatal -- it falls back to
    a null caption for that scene rather than aborting feature extraction
    for the whole film, consistent with every other stage's kill-switch
    philosophy in this pipeline.
    """
    output_dir = Path(output_dir)
    keyframe_dir = output_dir / "keyframes"
    keyframe_dir.mkdir(parents=True, exist_ok=True)

    scenes_with_stems = []
    for scene in scenes:
        sid = scene["scene_id"]
        stems = []
        for (s, stem_name), path in stem_audio_paths.items():
            if s == sid:
                features = extract_stem_features(str(path))
                # harness only needs name/energy/has_transients per its
                # SYSTEM_PROMPT contract - trim to that rather than
                # passing every extractor field
                stems.append({
                    "name": stem_name,
                    "energy": features["energy"],
                    "has_transients": features["has_transients"],
                })

        frame_path = keyframe_dir / f"scene_{sid}_keyframe.jpg"
        midpoint = scene["start"] + scene["duration"] / 2
        try:
            extract_keyframe(video_path, frame_path, timestamp=midpoint)
            visual_caption = caption_scene(frame_path)
        except Exception as e:
            print(f"WARNING: auto-captioning failed for scene {sid} ({e}) -- "
                  f"visual_caption will be null for this scene", file=sys.stderr)
            visual_caption = None

        scenes_with_stems.append({
            "scene_id": sid,
            "stems": stems,
            "visual_caption": visual_caption,
        })

    out_path = output_dir / "scenes_with_features.json"
    out_path.write_text(json.dumps(scenes_with_stems, indent=2))
    return scenes_with_stems


def stage_agent(scenes_with_stems):
    """Runs the placement-reasoning agent. TESTED against a mock server
    including malformed-JSON retry recovery; point LLM_BASE_URL at your
    real vLLM server before calling this for real."""
    results = run_pipeline(scenes_with_stems)
    coherence = check_coherence(results)
    print(f"Coherence: {coherence['coherent_total']}/{coherence['total_recurring_checks']} "
          f"recurring placements coherent "
          f"({coherence['exact_match']} exact match, "
          f"{coherence['justified_change']} justified change, "
          f"{coherence['unjustified_change']} unjustified change)")
    return results, coherence


def stage_render(scene_results, stem_audio_paths, scene_durations, output_dir, target="5.1"):
    """
    Kill-switch: tries the real ADM+EAR render first; ANY failure falls
    back to the FFmpeg channel-based render rather than aborting the
    pipeline. Both paths are individually tested (see SPEC.md Section 6);
    what's new here is only the try/except wiring between them.
    """
    output_dir = Path(output_dir)
    adm_path = output_dir / "film.adm.wav"
    rendered_path = output_dir / f"film_{target}.wav"
    fallback_path = output_dir / "film_fallback_5.1.wav"

    try:
        build_adm_bwf(scene_results, stem_audio_paths, scene_durations, adm_path)
        render_bwf(adm_path, rendered_path, target=target)
        print(f"ADM/EAR render succeeded: {rendered_path}")
        print(check_adm_coherence(adm_path))
        return rendered_path, "adm"
    except Exception:
        print("ADM/EAR render failed - falling back to FFmpeg 5.1. Traceback:")
        traceback.print_exc()
        render_5_1_fallback(scene_results, stem_audio_paths, scene_durations, fallback_path)
        print(f"FFmpeg fallback render succeeded: {fallback_path}")
        return fallback_path, "fallback"


def stage_binaural(rendered_path, target, output_dir):
    """Binaural stereo pass for headphone playback. TESTED against real
    EAR output using the synthetic HRIR set; test get_real_hrirs() first
    in your notebook per binaural_renderer.py's note."""
    from adm_renderer import TARGET_SYSTEMS
    output_dir = Path(output_dir)
    binaural_path = output_dir / "film_binaural.wav"
    system = TARGET_SYSTEMS.get(target, target)  # "5.1" -> "0+5+0", etc.
    hrirs = get_hrirs(prefer_real=True)  # falls back to synthetic on its own if this fails
    render_binaural(rendered_path, binaural_path, system=system, hrirs=hrirs)
    return binaural_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-video", required=True)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--target", default="5.1", choices=["5.1", "5.1.4"])
    parser.add_argument("--only", default=None,
                         help=f"Comma-separated subset of stages to run: {STAGE_ORDER}. "
                              f"Default runs all of them in order.")
    parser.add_argument("--launch-dashboard", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stages_to_run = args.only.split(",") if args.only else STAGE_ORDER

    scenes = stage_segment(args.input_video, output_dir) if "segment" in stages_to_run else \
        json.loads((output_dir / "scenes.json").read_text())

    stem_audio_paths = {}
    if "separate" in stages_to_run:
        stem_audio_paths = stage_separate(args.input_video, scenes, output_dir)
    elif (output_dir / "stem_manifest.json").exists():
        manifest = json.loads((output_dir / "stem_manifest.json").read_text())
        stem_audio_paths = {tuple([int(k.split(":")[0]), k.split(":")[1]]): Path(v)
                             for k, v in manifest.items()}

    scenes_with_stems = stage_features(args.input_video, scenes, stem_audio_paths, output_dir) \
        if "features" in stages_to_run else \
        json.loads((output_dir / "scenes_with_features.json").read_text())

    if "agent" in stages_to_run:
        scene_results, coherence = stage_agent(scenes_with_stems)
    else:
        scene_results = [json.loads(p.read_text())
                          for p in sorted(output_dir.glob("scene_*_placements.json"))]

    scene_durations = {s["scene_id"]: s["duration"] for s in scenes}

    rendered_path = None
    if "render" in stages_to_run:
        rendered_path, render_mode = stage_render(
            scene_results, stem_audio_paths, scene_durations, output_dir, target=args.target
        )

    if "binaural" in stages_to_run and rendered_path:
        stage_binaural(rendered_path, args.target, output_dir)

    if args.launch_dashboard or "dashboard" in stages_to_run:
        from dashboard import build_app
        app = build_app(output_dir, output_dir)
        app.launch()


if __name__ == "__main__":
    sys.exit(main())
