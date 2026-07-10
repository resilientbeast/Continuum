"""
Binaural rendering stage — the piece EAR itself doesn't provide.

EAR (adm_renderer.py) renders ADM objects to a BS.2051 speaker layout
(e.g. 6-channel 5.1 or 10-channel 5.1.4) as plain multichannel PCM. That's
correct object-based rendering, but it's speaker-layout audio, not
headphone audio - and judges will almost certainly listen on headphones.

This module closes that gap: convolve each rendered speaker channel with
a Head-Related Impulse Response (HRIR) for that speaker's known position,
sum across channels, output 2-channel binaural.

Requires: pip install spaudiopy scipy soundfile numpy

HRTF data note (read this before you run it):
`spaudiopy.io.load_hrirs()` downloads a real measured HRTF set (TU Berlin,
DOI 10.14279/depositonce-5718.5) from depositonce.tu-berlin.de at first
use. That domain was unreachable from the sandbox this module was tested
in, so the download itself could NOT be verified end-to-end here - test
`get_real_hrirs()` first thing once you're in the notebook (normal
internet access), since that's the one line in this file that wasn't
directly observed working. Everything downstream of it (grid lookup,
convolution, channel summing) WAS tested, using the library's built-in
synthetic HRIR generator as a stand-in data source for the same code
path. If the real download fails in your environment too, `get_hrirs()`
automatically falls back to the synthetic set and prints a warning -
the render will still complete, just with lower perceptual quality.
"""

import math
import warnings

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve

import spaudiopy as spa


# BS.2051 speaker azimuth/elevation, confirmed earlier against EAR's own
# 2051_layouts.yaml. Order matters - must match the channel order
# ear-render actually writes for that system.
SPEAKER_LAYOUTS = {
    "0+5+0": [  # plain 5.1 - de-risked baseline
        ("M+030", 30.0, 0.0),
        ("M-030", -30.0, 0.0),
        ("M+000", 0.0, 0.0),
        ("LFE1", None, None),   # non-directional, handled separately
        ("M+110", 110.0, 0.0),
        ("M-110", -110.0, 0.0),
    ],
    "4+5+0": [  # 5.1.4 - includes height, needed for "overhead"
        ("M+030", 30.0, 0.0),
        ("M-030", -30.0, 0.0),
        ("M+000", 0.0, 0.0),
        ("LFE1", None, None),
        ("M+110", 110.0, 0.0),
        ("M-110", -110.0, 0.0),
        ("U+030", 30.0, 30.0),
        ("U-030", -30.0, 30.0),
        ("U+110", 110.0, 30.0),
        ("U-110", -110.0, 30.0),
    ],
}


def get_real_hrirs(fs=48000):
    """
    Fetches the real measured HRTF set. TEST THIS FIRST in your notebook -
    it needs to reach depositonce.tu-berlin.de, which this module's
    development sandbox could not reach.
    """
    return spa.io.load_hrirs(fs=fs, filename=None)


def get_hrirs(fs=48000, prefer_real=True):
    """
    Tries the real measured HRTF set first; falls back to spaudiopy's
    built-in synthetic (ITD/ILD model) set if the download fails, so a
    blocked network doesn't take down your whole render.
    """
    if prefer_real:
        try:
            return get_real_hrirs(fs=fs)
        except Exception as e:
            warnings.warn(
                f"Real HRTF download failed ({e}); falling back to the "
                f"synthetic HRIR set. Binaural output will still work, "
                f"just with a less realistic head model. Try "
                f"get_real_hrirs() directly once you have normal internet "
                f"access to confirm whether this was transient."
            )
    return spa.io.load_hrirs(fs=fs, filename="dummy")


def _to_grid(azimuth_deg, elevation_deg):
    """BS.2127 (azimuth: 0=front,+=left; elevation: 0=horizon,+=up) ->
    spaudiopy grid (azi radians CCW-positive from front, zen=colatitude
    from zenith in radians). Confirmed empirically: a +30deg (left)
    source produces higher left-ear than right-ear HRIR energy."""
    azi = math.radians(azimuth_deg) % (2 * math.pi)
    zen = math.pi / 2 - math.radians(elevation_deg)
    return azi, zen


def render_binaural(speaker_wav_path, output_path, system="0+5+0",
                     hrirs=None, lfe_gain_db=-6.0):
    """
    speaker_wav_path: the file produced by adm_renderer.render_bwf()
        (or ffmpeg_fallback's 5.1 output - same channel layout applies).
    system: must match whatever target you rendered to ("0+5+0" or
        "4+5+0") - this determines both the channel count AND the
        per-channel positions used for the HRIR lookup.
    hrirs: pass a pre-loaded spa.sig.HRIRs to avoid reloading/redownloading
        per call if you're rendering many files; defaults to get_hrirs().
    lfe_gain_db: LFE has no meaningful direction - summed to both ears
        at reduced gain rather than spatialized, which is standard
        practice for binaural downmixing.
    """
    if system not in SPEAKER_LAYOUTS:
        raise ValueError(f"Unknown system '{system}'. Known: {list(SPEAKER_LAYOUTS)}")
    layout = SPEAKER_LAYOUTS[system]

    audio, sr = sf.read(str(speaker_wav_path), always_2d=True)
    if audio.shape[1] != len(layout):
        raise ValueError(
            f"{speaker_wav_path} has {audio.shape[1]} channels, but system "
            f"'{system}' expects {len(layout)}. Wrong target passed?"
        )

    if hrirs is None:
        hrirs = get_hrirs(fs=sr)
    elif hrirs.fs != sr:
        raise ValueError(f"HRIR set is {hrirs.fs}Hz but audio is {sr}Hz")

    n_out = audio.shape[0] + hrirs.left.shape[1] - 1
    out_l = np.zeros(n_out, dtype=np.float64)
    out_r = np.zeros(n_out, dtype=np.float64)
    lfe_gain = 10 ** (lfe_gain_db / 20.0)

    for ch_idx, (name, az, el) in enumerate(layout):
        channel_signal = audio[:, ch_idx].astype(np.float64)
        if np.allclose(channel_signal, 0.0):
            continue  # skip silent channels - saves real convolution time

        if az is None:  # LFE
            out_l[:audio.shape[0]] += channel_signal * lfe_gain
            out_r[:audio.shape[0]] += channel_signal * lfe_gain
            continue

        azi, zen = _to_grid(az, el)
        h_l, h_r = hrirs.nearest_hrirs(azi, zen)
        out_l += fftconvolve(channel_signal, h_l)
        out_r += fftconvolve(channel_signal, h_r)

    stereo = np.stack([out_l, out_r], axis=1)
    peak = np.max(np.abs(stereo))
    if peak > 1.0:
        stereo = stereo / peak * 0.98  # headroom, avoid clipping after summing channels

    sf.write(str(output_path), stereo.astype(np.float32), sr)
    return output_path
