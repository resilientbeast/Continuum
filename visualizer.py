import argparse
import json
import os
from pathlib import Path
import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.style.use("dark_background")

CHANNEL_AZIMUTH = {
    "center": 0.0,
    "left": 30.0,
    "right": -30.0,
    "surround_left": 110.0,
    "surround_right": -110.0,
    "rear_left": 135.0,
    "rear_right": -135.0,
    "overhead": 0.0,
    "bed_full": 0.0,
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
    "bed_full": 0.0,
}

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
        
    stem_tracks = {}
    for r in placements:
        sid = r["scene_id"]
        for p in r["placements"]:
            stem = p["stem"]
            chan = p["channel"]
            if stem not in stem_tracks:
                stem_tracks[stem] = {"x": [], "y": []}
            stem_tracks[stem]["x"].append(sid)
            stem_tracks[stem]["y"].append(CHANNEL_AZIMUTH.get(chan, 0.0))
            
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_facecolor('#0f172a') # Tailwind slate-950
    fig.patch.set_facecolor('#0f172a')
    
    colors = ['#6366f1', '#a855f7', '#ec4899', '#14b8a6', '#f59e0b', '#3b82f6']
    
    for i, (stem, data) in enumerate(stem_tracks.items()):
        color = colors[i % len(colors)]
        ax.plot(data["x"], data["y"], marker='o', label=stem, linewidth=2, color=color, markersize=8)
        
    ax.set_title("Cross-Scene Coherence Timeline", color="white", pad=20, fontsize=14)
    ax.set_xlabel("Scene Number", color="#94a3b8")
    ax.set_ylabel("Azimuth Angle (Degrees)", color="#94a3b8")
    ax.set_ylim(-180, 180)
    ax.set_yticks([-135, -110, -30, 0, 30, 110, 135])
    ax.set_yticklabels(['Rear R (-135°)', 'Surr R (-110°)', 'Right (-30°)', 'Center (0°)', 'Left (30°)', 'Surr L (110°)', 'Rear L (135°)'], color="#cbd5e1")
    ax.tick_params(axis='x', colors="#cbd5e1")
    
    ax.grid(True, axis='y', linestyle='--', alpha=0.2, color="#cbd5e1")
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#334155')
    ax.spines['bottom'].set_color('#334155')
    
    ax.legend(facecolor='#1e293b', edgecolor='#334155', labelcolor="white", loc='upper right', bbox_to_anchor=(1.25, 1))
    
    fig.tight_layout()
    fig.savefig(job_dir / "coherence_plot.png", dpi=150, transparent=True)
    plt.close(fig)


def plot_trajectory(job_dir, placements):
    if not placements:
        return
        
    stem_tracks = {}
    for r in placements:
        sid = r["scene_id"]
        for p in r["placements"]:
            stem = p["stem"]
            chan = p["channel"]
            if stem not in stem_tracks:
                stem_tracks[stem] = {"az": [], "el": [], "sids": []}
            stem_tracks[stem]["az"].append(CHANNEL_AZIMUTH.get(chan, 0.0))
            stem_tracks[stem]["el"].append(CHANNEL_ELEVATION.get(chan, 0.0))
            stem_tracks[stem]["sids"].append(sid)
            
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'projection': 'polar'})
    ax.set_facecolor('#0f172a')
    fig.patch.set_facecolor('#0f172a')
    
    colors = ['#6366f1', '#a855f7', '#ec4899', '#14b8a6', '#f59e0b', '#3b82f6']
    
    for i, (stem, data) in enumerate(stem_tracks.items()):
        color = colors[i % len(colors)]
        
        theta = np.radians(data["az"]) 
        r = 90.0 - np.array(data["el"])
        
        ax.plot(theta, r, marker='o', label=stem, color=color, linewidth=2, markersize=8, alpha=0.8)
        
        if len(data["sids"]) > 1 and (data["az"][0] != data["az"][-1] or data["el"][0] != data["el"][-1]):
            ax.annotate(f"S{data['sids'][0]}", (theta[0], r[0]), textcoords="offset points", xytext=(5,5), color=color, fontsize=9)
            ax.annotate(f"S{data['sids'][-1]}", (theta[-1], r[-1]), textcoords="offset points", xytext=(5,5), color=color, fontsize=9)

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(1)
    
    ax.set_rgrids([30, 60, 90], labels=['60°', '30°', '0° Elv'], color="#64748b", angle=45)
    ax.set_thetagrids([0, 30, 90, 110, 135, 180, 225, 250, 270, 330], 
                      labels=['C', 'L', 'L-Side', 'Surr-L', 'Rear-L', 'Back', 'Rear-R', 'Surr-R', 'R-Side', 'R'], 
                      color="#cbd5e1")
                      
    ax.grid(color='#334155', linestyle='--', alpha=0.6)
    ax.spines['polar'].set_color('#334155')
    
    ax.set_title("Object Trajectories (Azimuth / Elevation)", color="white", pad=30, fontsize=14)
    ax.legend(facecolor='#1e293b', edgecolor='#334155', labelcolor="white", loc='upper left', bbox_to_anchor=(1.1, 1))
    
    fig.tight_layout()
    fig.savefig(job_dir / "trajectory_plot.png", dpi=150, transparent=True)
    plt.close(fig)


def plot_hrtf(job_dir):
    try:
        import spaudiopy as spa
        hrirs = spa.io.load_hrirs(fs=48000, filename='dummy')
        
        idx = 15
        
        ir_l = hrirs.left[idx][:100]
        ir_r = hrirs.right[idx][:100]
        
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.set_facecolor('#0f172a')
        fig.patch.set_facecolor('#0f172a')
        
        ax.plot(ir_l, label='Left Ear', color='#6366f1', linewidth=2)
        ax.plot(ir_r, label='Right Ear', color='#ec4899', linewidth=2, alpha=0.8)
        
        ax.set_title("Binaural HRTF ITD/ILD Example", color="white", pad=20, fontsize=14)
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
    plot_trajectory(job_dir, placements)
    plot_hrtf(job_dir)
