"""
Scene-by-scene placement reasoning harness with cross-scene coherence memory.
Feeds separated stems + scene metadata to an LLM agent, persists memory across scenes.

Runs against an OpenAI-compatible LLM endpoint.

Point this at the Fireworks API using env vars:

    export LLM_BASE_URL="https://api.fireworks.ai/inference/v1"
    export LLM_API_KEY="your-fireworks-api-key"
    export LLM_MODEL="accounts/fireworks/models/gemma-2-9b-it"
"""

import json
import os
import time
from pathlib import Path

from openai import OpenAI, APIConnectionError, APIStatusError

client = OpenAI(
    api_key=os.environ.get("LLM_API_KEY", "EMPTY"),
    base_url=os.environ.get("LLM_BASE_URL", "https://api.fireworks.ai/inference/v1"),
)
import re

MODEL = os.environ.get("LLM_MODEL", "accounts/fireworks/models/deepseek-v4-pro").strip('\"\' ')

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

SYSTEM_PROMPT = """You are a spatial audio placement agent for cinematic Continuum/5.1 mixing.
For each scene, decide channel/object placement for each audio stem provided.
Always check the coherence memory first - if a stem's audio signature matches a
previously logged recurring element (a motif, ambient bed, or character voice),
REUSE its established placement unless the visual context clearly justifies a change.

When you log a recurring element to memory, use the stem's own name as the memory
key (not an invented name) so it can be tracked automatically across scenes.

If a recurring stem's placement changes from what memory has recorded for it, you
MUST update memory_updates for that stem's key with the new channel_pattern, and
your rationale must state why the change is justified (e.g. the sound now reads
as muffled, distant, or behind an obstruction). Do not change an established
placement without logging the update -- an unlogged change is treated as an
error, not a deliberate creative choice.

If visual_caption is null (visual analysis unavailable for this scene), reason from
the stems and coherence memory alone - do not invent or assume visual details.

Valid channels: center, left, right, surround_left, surround_right, rear_left, rear_right, bed_full, overhead.
Output STRICT JSON only, matching this schema, with no markdown fences and no
commentary before or after the JSON:
{
  "scene_id": <int>,
  "placements": [
    {"stem": "<name>", "channel": "<channel>", "rationale": "<one sentence>"}
  ],
  "memory_updates": {
    "<stem_name>": {"first_seen": <scene_id>, "channel_pattern": "<channel>"}
  }
}
"""


def load_memory(output_dir):
    mem_path = output_dir / "coherence_memory.json"
    if mem_path.exists():
        return json.loads(mem_path.read_text())
    return {}


def save_memory(memory, output_dir):
    mem_path = output_dir / "coherence_memory.json"
    mem_path.parent.mkdir(exist_ok=True, parents=True)
    mem_path.write_text(json.dumps(memory, indent=2))


def build_user_prompt(scene_id, stems, visual_caption, memory):
    return json.dumps({
        "scene_id": scene_id,
        "stems": stems,
        "visual_caption": visual_caption,
        "current_coherence_memory": memory
    }, indent=2)


def _extract_json(raw_text):
    """
    Extract JSON from potentially fenced model output.
    """
    text = raw_text.strip()
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def process_scene(scene_id, stems, visual_caption=None, output_dir=None):
    """
    stems: list of dicts, e.g.
      [{"name": "dialogue", "energy": "medium", "has_transients": False},
       {"name": "alarm_sfx", "energy": "high", "has_transients": True}]
    """
    if output_dir is None:
        output_dir = Path("output")
    else:
        output_dir = Path(output_dir)

    memory = load_memory(output_dir)
    user_prompt = build_user_prompt(scene_id, stems, visual_caption, memory)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            result = _extract_json(response.choices[0].message.content)
            break
        except (APIConnectionError, APIStatusError) as e:
            last_error = e
            print(f"Scene {scene_id}: attempt {attempt}/{MAX_RETRIES} - "
                  f"LLM server unreachable or errored ({e}). "
                  f"Check your API URL and key.")
        except json.JSONDecodeError as e:
            last_error = e
            print(f"Scene {scene_id}: attempt {attempt}/{MAX_RETRIES} - "
                  f"model returned invalid JSON: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    else:
        raise RuntimeError(
            f"Scene {scene_id} failed after {MAX_RETRIES} attempts: {last_error}"
        )

    memory.update(result.get("memory_updates", {}))
    save_memory(memory, output_dir)

    out_path = output_dir / f"scene_{scene_id}_placements.json"
    out_path.write_text(json.dumps(result, indent=2))

    return result


def run_pipeline(scenes, output_dir=None):
    """
    scenes: ordered list of dicts, e.g.
      [{"scene_id": 1, "stems": [...], "visual_caption": "..."}, ...]
    """
    if output_dir is None:
        output_dir = Path("output")
    else:
        output_dir = Path(output_dir)

    mem_path = output_dir / "coherence_memory.json"
    if mem_path.exists():
        mem_path.unlink()  # fresh run

    all_results = []
    for scene in scenes:
        result = process_scene(scene["scene_id"], scene["stems"], scene.get("visual_caption"), output_dir)
        all_results.append(result)
        print(f"Scene {scene['scene_id']}: {len(result['placements'])} placements logged")

    return all_results


def check_coherence(all_results):
    """
    For each recurring stem (same name appearing in more than one scene),
    classifies each reappearance as one of:

      - exact_match: channel is identical to its previous appearance
      - justified_change: channel differs, but the agent logged a
        memory_updates entry for this stem in this scene -- i.e. it
        consciously re-authored the placement rather than drifting
      - unjustified_change: channel differs with no corresponding
        memory_updates entry -- this is the real failure mode

    Conflating "changed for a documented reason" with "changed silently"
    would either understate a deliberate creative decision (e.g. an alarm
    moving from beside you to muffled-behind-a-door as the scene cuts to
    an exterior) or overstate coherence by hiding an actual bug. Reporting
    them separately keeps both numbers honest.
    """
    seen_channels = {}
    exact_match = 0
    justified_change = 0
    unjustified_change = 0
    total_recurring = 0

    for r in all_results:
        memory_updates_this_scene = r.get("memory_updates", {})
        for p in r["placements"]:
            stem = p["stem"]
            channel = p["channel"]

            if stem in seen_channels:
                total_recurring += 1
                if seen_channels[stem] == channel:
                    exact_match += 1
                elif stem in memory_updates_this_scene:
                    justified_change += 1
                else:
                    unjustified_change += 1

            seen_channels[stem] = channel

    coherent_total = exact_match + justified_change

    return {
        "total_recurring_checks": total_recurring,
        "exact_match": exact_match,
        "justified_change": justified_change,
        "unjustified_change": unjustified_change,
        "coherent_total": coherent_total,
        "coherent_ratio": round(coherent_total / total_recurring, 2) if total_recurring else None
    }


if __name__ == "__main__":
    example_scenes = [
        {"scene_id": 1, "stems": [{"name": "ambient_hum", "energy": "low", "has_transients": False}],
         "visual_caption": "Empty corridor, flickering lights."},
        {"scene_id": 2, "stems": [{"name": "dialogue", "energy": "medium", "has_transients": False},
                                   {"name": "ambient_hum", "energy": "low", "has_transients": False}],
         "visual_caption": "Character at console, speaks one line."},
    ]
    results = run_pipeline(example_scenes)
    print(json.dumps(check_coherence(results), indent=2))
