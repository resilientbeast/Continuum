import argparse
import json
from pathlib import Path
import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

plt.style.use("dark_background")

# "bed_full" is intentionally absent from these two dicts. It's a
# full-surround ambient bed, not a directional position - plotting it as a
# point at 0deg azimuth (its old default via .get(chan, 0.0)) falsely
# implied it was placed identically to "center". It's handled separately
# below (NON_DIRECTIONAL_CHANNELS) and shown only as a legend entry, never
# as a point on either chart.
CHANNEL_AZIMUTH = {
    "center": 0.0,
    "left": 30.0,
    "right": -30.0,
    "surround_left": 110.0,
    "surround_right": -110.0,
    "rear_left": 135.0,
    "rear_right": -135.0,
    "overhead": 0.0,
}

CHANNEL_ELEVATION = {
    "center": 0.0,
    "left": 0.0,
    "right": 0.0,
    "surround_left": 0.0,
    "surround_right": 0.0,
    "rear_left": 0.0,
    "rear_right": 0.0,
    "overhead": 90.0,
}

NON_DIRECTIONAL_CHANNELS = {"bed_full"}

COLORS = ['#6366f1', '#a855f7', '#ec4899', '#14b8a6', '#f59e0b', '#3b82f6']
LINESTYLES = ['-', '--', '-.', ':']
MARKERS = ['o', 's', '^', 'D']


def load_placements(job_dir):
    placements = []
    for p in job_dir.glob("scene_*_placements.json"):
        try:
            sid = int(p.stem.split("_")[1])
            with open(p, 'r') as f:
                data = json.load(f)
                placements.append({"scene_id": sid, "placements": data.get("placements", [])})
        except Exception:
            pass
    return sorted(placements, key=lambda x: x["scene_id"])


def plot_coherence_timeline(job_dir, placements):
    if not placements:
        return

    directional = {}
    bed_scene_ids = {}

    for r in placements:
        sid = r["scene_id"]
        for p in r["placements"]:
            stem = p["stem"]
            chan = p["channel"]
            if chan in NON_DIRECTIONAL_CHANNELS:
                bed_scene_ids.setdefault(stem, []).append(sid)
                continue
            directional.setdefault(stem, {"x": [], "y": []})
            directional[stem]["x"].append(sid)
            directional[stem]["y"].append(CHANNEL_AZIMUTH.get(chan, 0.0))

    all_stems = list(dict.fromkeys(list(directional.keys()) + list(bed_scene_ids.keys())))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_facecolor('#0f172a')
    fig.patch.set_facecolor('#0f172a')

    legend_handles = []

    for i, stem in enumerate(all_stems):
        color = COLORS[i % len(COLORS)]
        # Distinct linestyle + marker per stem, plus alpha < 1, so that
        # stems sharing the same azimuth for long stretches (e.g. several
        # stems all sitting at "center") stay visually distinguishable
        # instead of the last-drawn series fully hiding the others.
        if stem in directional and directional[stem]["x"]:
            # Add a small vertical jitter so identically-placed stems remain visually parallel
            jitter = (i - len(all_stems) / 2) * 1.5
            jittered_y = [y + jitter for y in directional[stem]["y"]]
            
            ax.plot(
                directional[stem]["x"], jittered_y,
                marker=MARKERS[i % len(MARKERS)],
                linestyle=LINESTYLES[i % len(LINESTYLES)],
                linewidth=2, color=color, markersize=6, alpha=0.85,
                zorder=3,
            )
            legend_handles.append(Line2D(
                [0], [0], color=color, marker=MARKERS[i % len(MARKERS)],
                linestyle=LINESTYLES[i % len(LINESTYLES)], label=stem,
            ))
        if stem in bed_scene_ids:
            n = len(bed_scene_ids[stem])
            legend_handles.append(Line2D(
                [0], [0], color=color, linewidth=8, alpha=0.4,
                label=f"{stem} (full ambient bed, {n} scenes - not a point)",
            ))

    ax.set_title("Cross-Scene Coherence Timeline", color="white", pad=20, fontsize=14)
    ax.set_xlabel("Scene Number", color="#94a3b8")
    ax.set_ylabel("Azimuth Angle (Degrees)", color="#94a3b8")
    ax.set_ylim(-180, 180)
    ax.set_yticks([-135, -110, -30, 0, 30, 110, 135])
    ax.set_yticklabels(
        ['Rear R (-135°)', 'Surr R (-110°)', 'Right (-30°)', 'Center (0°)', 'Left (30°)', 'Surr L (110°)', 'Rear L (135°)'],
        color="#cbd5e1"
    )
    ax.tick_params(axis='x', colors="#cbd5e1")

    ax.grid(True, axis='y', linestyle='--', alpha=0.2, color="#cbd5e1")
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#334155')
    ax.spines['bottom'].set_color('#334155')

    ax.legend(handles=legend_handles, facecolor='#1e293b', edgecolor='#334155',
              labelcolor="white", loc='upper right', bbox_to_anchor=(1.4, 1))

    fig.tight_layout()
    fig.savefig(job_dir / "coherence_plot.png", dpi=150, transparent=True)
    plt.close(fig)


def plot_positions(job_dir, placements):
    """
    Renamed from plot_trajectory: these are discrete per-scene placement
    snapshots, not continuous intra-scene motion - the pipeline doesn't
    track sub-scene movement, so "trajectory" overstated what this shows.
    """
    if not placements:
        return

    stem_polar = {}
    bed_scene_ids = {}

    for r in placements:
        sid = r["scene_id"]
        for p in r["placements"]:
            stem = p["stem"]
            chan = p["channel"]
            if chan in NON_DIRECTIONAL_CHANNELS:
                bed_scene_ids.setdefault(stem, []).append(sid)
                continue
            stem_polar.setdefault(stem, {"az": [], "el": [], "sids": []})
            stem_polar[stem]["az"].append(CHANNEL_AZIMUTH.get(chan, 0.0))
            stem_polar[stem]["el"].append(CHANNEL_ELEVATION.get(chan, 0.0))
            stem_polar[stem]["sids"].append(sid)

    all_stems = list(dict.fromkeys(list(stem_polar.keys()) + list(bed_scene_ids.keys())))

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    ax.set_facecolor('#0f172a')
    fig.patch.set_facecolor('#0f172a')

    legend_handles = []

    for i, stem in enumerate(all_stems):
        color = COLORS[i % len(COLORS)]

        if stem in stem_polar and stem_polar[stem]["az"]:
            data = stem_polar[stem]
            # Add a small angular jitter so identical points don't swallow each other
            jitter_deg = (i - len(all_stems) / 2) * 4.0
            theta = np.radians([az + jitter_deg for az in data["az"]])
            r = 90.0 - np.array(data["el"])

            ax.plot(theta, r, marker=MARKERS[i % len(MARKERS)], color=color,
                    linestyle='none', markersize=8, alpha=0.8, zorder=3)
            legend_handles.append(Line2D(
                [0], [0], color=color, marker=MARKERS[i % len(MARKERS)], label=stem,
            ))

            if len(data["sids"]) > 1 and (data["az"][0] != data["az"][-1] or data["el"][0] != data["el"][-1]):
                ax.annotate(f"S{data['sids'][0]}", (theta[0], r[0]), textcoords="offset points", xytext=(5, 5), color=color, fontsize=9)
                ax.annotate(f"S{data['sids'][-1]}", (theta[-1], r[-1]), textcoords="offset points", xytext=(5, 5), color=color, fontsize=9)

        if stem in bed_scene_ids:
            n = len(bed_scene_ids[stem])
            legend_handles.append(Line2D(
                [0], [0], color=color, linewidth=8, alpha=0.4,
                label=f"{stem} (full ambient bed, {n} scenes - omitted, not a point)",
            ))

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(1)

    ax.set_rgrids([30, 60, 90], labels=['60°', '30°', '0° Elv'], color="#64748b", angle=45)
    ax.set_thetagrids(
        [0, 30, 90, 110, 135, 180, 225, 250, 270, 330],
        labels=['C', 'L', 'L-Side', 'Surr-L', 'Rear-L', 'Back', 'Rear-R', 'Surr-R', 'R-Side', 'R'],
        color="#cbd5e1"
    )

    ax.grid(color='#334155', linestyle='--', alpha=0.6)
    ax.spines['polar'].set_color('#334155')

    ax.set_title("Object Positions (Azimuth / Elevation)", color="white", pad=30, fontsize=14)
    ax.legend(handles=legend_handles, facecolor='#1e293b', edgecolor='#334155',
              labelcolor="white", loc='upper left', bbox_to_anchor=(1.1, 1))

    fig.tight_layout()
    fig.savefig(job_dir / "trajectory_plot.png", dpi=150, transparent=True)
    plt.close(fig)


def plot_hrtf(job_dir):
    try:
        import spaudiopy as spa

        source_label = "measured HRTF"
        try:
            hrirs = spa.io.load_hrirs(fs=48000)  # real measured set; needs network access
        except Exception:
            hrirs = spa.io.load_hrirs(fs=48000, filename='dummy')  # synthetic fallback
            source_label = "synthetic HRTF model (measured set unavailable at render time)"

        idx = 15

        # Report the actual position this index corresponds to instead of
        # a bare magic number - verify the attribute name against your
        # installed spaudiopy version if this differs (grid layout has
        # changed across versions).
        position_label = f"measurement index {idx}"
        try:
            az_deg, el_deg = np.degrees(hrirs.grid[idx][:2])
            position_label = f"{az_deg:.0f}° azimuth, {el_deg:.0f}° elevation"
        except Exception:
            pass

        ir_l = hrirs.left[idx][:100]
        ir_r = hrirs.right[idx][:100]

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.set_facecolor('#0f172a')
        fig.patch.set_facecolor('#0f172a')

        ax.plot(ir_l, label='Left Ear', color='#6366f1', linewidth=2)
        ax.plot(ir_r, label='Right Ear', color='#ec4899', linewidth=2, alpha=0.8)

        ax.set_title(f"Binaural HRTF ITD/ILD -- {source_label}, source at {position_label}",
                     color="white", pad=20, fontsize=13)
        ax.set_xlabel("Samples (Time)", color="#94a3b8")
        ax.set_ylabel("Amplitude", color="#94a3b8")

        ax.grid(True, linestyle='--', alpha=0.2, color="#cbd5e1")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#334155')
        ax.spines['bottom'].set_color('#334155')

        ax.tick_params(colors="#cbd5e1")
        ax.legend(facecolor='#1e293b', edgecolor='#334155', labelcolor="white")

        fig.tight_layout()
        fig.savefig(job_dir / "hrtf_plot.png", dpi=150, transparent=True)
        plt.close(fig)
    except Exception as e:
        print(f"Failed to plot HRTF: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Job output directory")
    args = parser.parse_args()

    job_dir = Path(args.dir)
    placements = load_placements(job_dir)

    plot_coherence_timeline(job_dir, placements)
    plot_positions(job_dir, placements)
    plot_hrtf(job_dir)
