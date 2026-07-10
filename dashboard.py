"""
Static results dashboard for the spatial audio coherence pipeline.

Deliberately NOT a live pipeline trigger - it browses an already-computed
`output/` directory (scene_N_placements.json + coherence_memory.json +
whatever rendered audio files you produced). This is the safe choice for
a public-facing demo link: Track 3's live-demo URL is optional but
recommended, and a link that's only alive while your notebook session
happens to be running is worse than no link - this one keeps working off
whatever you point it at, GPU session or not.

Run:
    python3 dashboard.py --output-dir output --audio-dir .

Then either open the local URL, or pass share=True in launch() below for
a temporary public link if you want to demo it live during judging.

Requires: pip install gradio
"""

import argparse
import json
from pathlib import Path

import gradio as gr


def load_run(output_dir):
    """
    Reads whatever's actually in the output directory rather than
    assuming a fixed scene count - so this works whether you ran 2 test
    scenes or a full film.
    """
    output_dir = Path(output_dir)
    scene_files = sorted(output_dir.glob("scene_*_placements.json"),
                          key=lambda p: int(p.stem.split("_")[1]))

    scenes = []
    for f in scene_files:
        scenes.append(json.loads(f.read_text()))

    memory_path = output_dir / "coherence_memory.json"
    memory = json.loads(memory_path.read_text()) if memory_path.exists() else {}

    return scenes, memory


def compute_coherence_stat(scenes):
    """Same logic as placement_agent_harness.check_coherence(), duplicated
    here so the dashboard has zero import dependency on the harness (and
    therefore zero dependency on having a vLLM client configured just to
    browse results)."""
    seen_channels = {}
    matches, total = 0, 0
    for r in scenes:
        for p in r["placements"]:
            stem = p["stem"]
            if stem in seen_channels:
                total += 1
                if seen_channels[stem] == p["channel"]:
                    matches += 1
            seen_channels[stem] = p["channel"]
    return matches, total


def scene_choices(scenes):
    return [f"Scene {s['scene_id']}" for s in scenes]


def format_scene_table(scene):
    rows = [[p["stem"], p["channel"], p["rationale"]] for p in scene["placements"]]
    return rows


def format_memory_table(memory):
    return [[name, info["first_seen"], info["channel_pattern"]]
            for name, info in memory.items()]


def find_audio_files(audio_dir):
    """
    Looks for the known output filenames from adm_renderer / ffmpeg_fallback
    / binaural_renderer. Missing files just don't show a player - this
    doesn't assume every path was run.
    """
    audio_dir = Path(audio_dir)
    candidates = {
        "Binaural (headphones - recommended for judging)": "film_binaural.wav",
        "Object-based 5.1 (EAR render)": "film_5.1.wav",
        "Object-based 5.1.4 (EAR render, with height)": "film_5.1.4.wav",
        "Channel-based 5.1 fallback (FFmpeg)": "film_fallback_5.1.wav",
        "Raw ADM BW64 (metadata + audio, for ear-utils dump_axml)": "film.adm.wav",
    }
    found = {}
    for label, filename in candidates.items():
        path = audio_dir / filename
        if path.exists():
            found[label] = str(path)
    return found


def build_app(output_dir, audio_dir):
    scenes, memory = load_run(output_dir)
    audio_files = find_audio_files(audio_dir)

    if not scenes:
        raise SystemExit(
            f"No scene_*_placements.json files found in {output_dir}. "
            f"Run the pipeline first - this dashboard only browses "
            f"already-computed output, it doesn't run inference itself."
        )

    matches, total = compute_coherence_stat(scenes)
    coherence_summary = (
        f"**Coherence: {matches}/{total} recurring placements matched** "
        f"across {len(scenes)} scenes"
        if total > 0 else
        f"No recurring stems across these {len(scenes)} scenes yet - "
        f"coherence has nothing to prove or disprove here."
    )

    scene_lookup = {f"Scene {s['scene_id']}": s for s in scenes}

    with gr.Blocks(title="Spatial Audio Coherence — Pipeline Results") as app:
        gr.Markdown(
            "# Spatial Audio Coherence Agent — Results\n"
            "Cross-scene spatial placement for AI-generated film audio, "
            "with a placement-reasoning agent self-hosted via vLLM on an "
            "AMD MI300X. This viewer browses already-computed pipeline "
            "output — it does not trigger live inference or rendering."
        )
        gr.Markdown(coherence_summary)

        with gr.Row():
            with gr.Column(scale=1):
                scene_dropdown = gr.Dropdown(
                    choices=scene_choices(scenes),
                    value=scene_choices(scenes)[0],
                    label="Scene",
                )
                scene_table = gr.Dataframe(
                    headers=["Stem", "Channel", "Rationale"],
                    value=format_scene_table(scenes[0]),
                    label="Placements this scene",
                    interactive=False,
                    wrap=True,
                )

            with gr.Column(scale=1):
                gr.Markdown("### Coherence memory (recurring elements)")
                gr.Dataframe(
                    headers=["Element", "First seen (scene)", "Channel pattern"],
                    value=format_memory_table(memory),
                    interactive=False,
                    wrap=True,
                )

        gr.Markdown("### Rendered output")
        if audio_files:
            for label, path in audio_files.items():
                with gr.Row():
                    gr.Audio(value=path, label=label, interactive=False)
        else:
            gr.Markdown(
                f"*No rendered audio files found in `{audio_dir}`. Expected "
                f"one or more of: film_binaural.wav, film_5.1.wav, "
                f"film_5.1.4.wav, film_fallback_5.1.wav, film.adm.wav.*"
            )

        def on_scene_change(scene_label):
            return format_scene_table(scene_lookup[scene_label])

        scene_dropdown.change(on_scene_change, inputs=scene_dropdown, outputs=scene_table)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output",
                         help="Directory with scene_N_placements.json + coherence_memory.json")
    parser.add_argument("--audio-dir", default=".",
                         help="Directory containing the rendered audio files")
    parser.add_argument("--share", action="store_true",
                         help="Create a temporary public Gradio link (use only while "
                              "actively demoing - it expires with your session)")
    args = parser.parse_args()

    app = build_app(args.output_dir, args.audio_dir)
    app.launch(share=args.share)
