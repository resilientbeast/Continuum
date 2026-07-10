"""
Stem feature extraction: converts raw separated audio stems (from Demucs) into
the lightweight feature dicts consumed by the placement-reasoning agent harness.

Requires: librosa, numpy, soundfile
  pip3 install librosa soundfile numpy
"""

import numpy as np
import librosa
from pathlib import Path


def extract_stem_features(audio_path, sr=22050):
    """
    Loads a stem audio file and computes lightweight features used by the
    placement agent to reason about spatial placement.
    """
    y, sr = librosa.load(audio_path, sr=sr, mono=True)

    if len(y) == 0:
        return _empty_features(audio_path)

    rms = librosa.feature.rms(y=y)[0]
    mean_rms = float(np.mean(rms))
    energy_label = _bucket_energy(mean_rms)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    has_transients = len(onsets) > 3  # more than a few sharp attacks = transient-heavy

    # crude silence ratio - helps flag near-empty stems (e.g. no dialogue this scene)
    silence_ratio = float(np.mean(rms < 0.01))

    # spectral centroid as a rough "brightness" proxy - helps distinguish
    # e.g. high-pitched alarm SFX from low rumbling ambience
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    mean_centroid = float(np.mean(centroid))
    brightness_label = "bright" if mean_centroid > 3000 else ("mid" if mean_centroid > 1000 else "low")

    return {
        "name": Path(audio_path).stem,
        "energy": energy_label,
        "has_transients": bool(has_transients),
        "silence_ratio": round(silence_ratio, 2),
        "brightness": brightness_label,
        "duration_sec": round(len(y) / sr, 2)
    }


def _bucket_energy(mean_rms):
    if mean_rms < 0.02:
        return "low"
    elif mean_rms < 0.08:
        return "medium"
    return "high"


def _empty_features(audio_path):
    return {
        "name": Path(audio_path).stem,
        "energy": "low",
        "has_transients": False,
        "silence_ratio": 1.0,
        "brightness": "low",
        "duration_sec": 0.0
    }


def extract_scene_stems(scene_stem_dir):
    """
    Given a directory of separated stems for one scene (e.g. output from Demucs:
    vocals.wav, drums.wav, bass.wav, other.wav - or renamed per your naming scheme),
    returns the list of feature dicts ready to feed into the placement agent.
    """
    stem_dir = Path(scene_stem_dir)
    stem_files = sorted(stem_dir.glob("*.wav"))
    return [extract_stem_features(str(f)) for f in stem_files]


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python stem_features.py <scene_stem_directory>")
        sys.exit(1)

    features = extract_scene_stems(sys.argv[1])
    print(json.dumps(features, indent=2))
