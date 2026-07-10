"""
FFmpeg 5.1 channel-based fallback renderer.

This is the kill-switch safety net: if ADM generation / EAR rendering
(adm_renderer.py) isn't validated by your cutoff time, this path still
produces a real, honest 5.1 file from the exact same placement-agent
output - no object-based metadata, no coherence-in-the-ADM-XML claim,
just a channel-based mixdown. Takes the identical scene_results /
stem_audio_paths / scene_durations inputs as adm_renderer.build_adm_bwf
so switching paths is a one-line change in your pipeline driver, not a
rewrite.

Requires: ffmpeg on PATH, soundfile, numpy.

# Known simplification (say this explicitly in your README, don't hide
# it): the fallback path has no per-scene dynamic panning. It uses static 
# routing for the full runtime, always, picking the majority-voted channel 
# for each stem. Furthermore, plain 5.1 has no height layer and no diffuse 
# concept, so:
#   - "overhead" folds down to front center (no true height channel here -
#     that's exactly the gap true object-based rendering closes)
#   - "bed_full" is split evenly across FL/FC/FR at reduced gain as a
#     crude stand-in for "everywhere"
"""

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf


# Standard ffmpeg 5.1 channel order: FL FR FC LFE BL BR
CHANNEL_ROUTE = {
    "center":         {"FC": 1.0},
    "left":           {"FL": 1.0},
    "right":          {"FR": 1.0},
    "surround_left":  {"BL": 1.0},
    "surround_right": {"BR": 1.0},
    "overhead":       {"FC": 1.0},                       # no height in 5.1
    "bed_full":       {"FL": 0.5, "FC": 0.7, "FR": 0.5},  # crude "everywhere"
}
OUTPUT_CHANNELS = ["FL", "FR", "FC", "LFE", "BL", "BR"]


def _build_stem_tracks(scene_results, stem_audio_paths, scene_durations, sample_rate):
    """
    Same continuous-per-stem-track logic as adm_renderer.build_adm_bwf,
    duplicated here so this fallback has zero dependency on the ADM path -
    if that module is broken, this one must still work standalone.
    """
    scene_results = sorted(scene_results, key=lambda r: r["scene_id"])
    scene_ids = [r["scene_id"] for r in scene_results]

    scene_starts = {}
    t = 0.0
    for sid in scene_ids:
        scene_starts[sid] = t
        t += scene_durations[sid]
    total_duration = t
    total_samples = int(round(total_duration * sample_rate))

    stem_names = sorted({p["stem"] for r in scene_results for p in r["placements"]})
    stem_audio = {name: np.zeros(total_samples, dtype=np.float32) for name in stem_names}
    stem_channel_per_scene = {name: {} for name in stem_names}

    for r in scene_results:
        sid = r["scene_id"]
        start_sample = int(round(scene_starts[sid] * sample_rate))
        scene_len_samples = int(round(scene_durations[sid] * sample_rate))

        for p in r["placements"]:
            stem_name = p["stem"]
            key = (sid, stem_name)
            if key in stem_audio_paths:
                y, sr = sf.read(str(stem_audio_paths[key]), dtype="float32", always_2d=False)
                if sr != sample_rate:
                    raise ValueError(
                        f"Sample rate mismatch for {key}: file is {sr}Hz, expected {sample_rate}Hz"
                    )
                if y.ndim > 1:
                    y = y.mean(axis=1)
                n = min(len(y), scene_len_samples)
                stem_audio[stem_name][start_sample:start_sample + n] = y[:n]
            stem_channel_per_scene[stem_name][sid] = p["channel"]

    return stem_audio, stem_channel_per_scene, total_samples


def render_5_1_fallback(scene_results, stem_audio_paths, scene_durations,
                          output_path, sample_rate=48000):
    """
    Same call shape as adm_renderer.build_adm_bwf + render_bwf combined into
    one step, since there's no intermediate ADM file in this path.
    Returns output_path on success; raises on ffmpeg failure - don't swallow
    that, a failure here means even the safety net is broken.
    """
    stem_audio, stem_channel_per_scene, total_samples = _build_stem_tracks(
        scene_results, stem_audio_paths, scene_durations, sample_rate
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        stem_wav_paths = {}
        for name, audio in stem_audio.items():
            path = tmp / f"{name}.wav"
            sf.write(str(path), audio, sample_rate, subtype="PCM_16")
            stem_wav_paths[name] = path

        # Static routing for the full runtime, always. We route each stem
        # using whichever channel it used most often across all scenes. 
        # This simplification means the fallback path cannot express legitimate 
        # per-scene dynamic panning (unlike the ADM/EAR path).
        stem_primary_channel = {}
        for name, per_scene in stem_channel_per_scene.items():
            labels = list(per_scene.values())
            stem_primary_channel[name] = max(set(labels), key=labels.count)

        # build ffmpeg filter_complex: route + weight each stem into the
        # 6 output buses, then amix each bus down to one channel, then
        # amerge the 6 buses into one 5.1 interleaved output.
        inputs = []
        filter_parts = []
        bus_sources = {ch: [] for ch in OUTPUT_CHANNELS}

        for i, (name, path) in enumerate(stem_wav_paths.items()):
            inputs += ["-i", str(path)]
            route = CHANNEL_ROUTE[stem_primary_channel[name]]
            for ch, gain in route.items():
                label = f"s{i}_{ch}"
                filter_parts.append(f"[{i}:a]volume={gain}[{label}]")
                bus_sources[ch].append(f"[{label}]")

        merge_labels = []
        for ch in OUTPUT_CHANNELS:
            sources = bus_sources[ch]
            out_label = f"bus_{ch}"
            if not sources:
                # silent bus - generate silence matching total duration
                filter_parts.append(
                    f"anullsrc=r={sample_rate}:cl=mono:d={total_samples / sample_rate}[{out_label}]"
                )
            elif len(sources) == 1:
                filter_parts.append(f"{sources[0]}anull[{out_label}]")
            else:
                filter_parts.append(
                    f"{''.join(sources)}amix=inputs={len(sources)}:normalize=0[{out_label}]"
                )
            merge_labels.append(f"[{out_label}]")

        filter_parts.append(
            f"{''.join(merge_labels)}amerge=inputs={len(OUTPUT_CHANNELS)}"
            f"[merged]"
        )
        # amerge concatenates channels in input order, which matches
        # OUTPUT_CHANNELS order since we appended buses in that order -
        # tag the result with the correct 5.1 channel layout explicitly.
        filter_parts.append("[merged]channelmap=channel_layout=5.1[out]")

        filter_complex = ";".join(filter_parts)

        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    return output_path
