"""
Stem feature extraction: converts raw separated audio stems (from Demucs) into
the lightweight feature dicts consumed by the placement-reasoning agent harness.

Requires: librosa, numpy, soundfile
  pip3 install librosa soundfile numpy
"""

import numpy as np
import librosa
from pathlib import Path

# Onsets-per-second above this are considered "transient-heavy". Tuned as a
# starting point; validate against your own corpus (onset_rate is returned
# in the feature dict so you can inspect the actual distribution and retune).
ONSET_RATE_THRESHOLD = 1.5

# Peak-picking sensitivity for onset_detect. Higher = fewer, stronger-only
# onsets. Demucs separation leakage (residual bleed from other stems) can
# register as spurious low-amplitude onsets at the default delta, which is
# what was making has_transients saturate to True almost everywhere.
ONSET_DELTA = 0.07


def extract_stem_features(audio_path, sr=22050):
    """
    Loads a stem audio file and computes lightweight features used by the
    placement agent to reason about spatial placement.
    """
    y, sr = librosa.load(audio_path, sr=sr, mono=True)

    if len(y) == 0:
        return _empty_features(audio_path)

    duration_sec = len(y) / sr

    rms = librosa.feature.rms(y=y)[0]
    mean_rms = float(np.mean(rms))
    energy_label = _bucket_energy(mean_rms)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        delta=ONSET_DELTA,
    )

    # Rate, not raw count - a 9s scene and a 0.6s scene need different
    # absolute onset counts to represent the same actual transient density.
    onset_rate = float(len(onsets) / duration_sec) if duration_sec > 0 else 0.0
    has_transients = onset_rate > ONSET_RATE_THRESHOLD

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
        "onset_rate": round(onset_rate, 2),
        "silence_ratio": round(silence_ratio, 2),
        "brightness": brightness_label,
        "duration_sec": round(duration_sec, 2)
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
        "onset_rate": 0.0,
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
