"""
caption_extractor.py

Automatic replacement for hand-authored visual_caption. Extracts a
representative keyframe from each scene's source video clip via ffmpeg,
then captions it using a vision-language model served through Fireworks
on the same OpenAI-compatible API surface as placement_agent_harness.py's
reasoning model.

Requires: ffmpeg + ffprobe on PATH (already in the project Dockerfile).

Env vars:
  VISION_LLM_BASE_URL   https://api.fireworks.ai/inference/v1
  VISION_LLM_API_KEY    Your Fireworks API key
  VISION_LLM_MODEL      default: accounts/fireworks/models/kimi-k2p6

NOTE: the docstring in the prior version of this file documented a default
of accounts/fireworks/models/llama-v3p2-11b-vision-instruct, but the code
had accounts/fireworks/models/kimi-k2p6 hardcoded. Confirm which one you
actually intend to use going forward and update whichever side is stale -
this fix keeps kimi-k2p6 (since that's what generated your existing scene
dataset) and makes it behave correctly, but llama-v3p2-11b-vision-instruct
is a simpler option if you'd rather not deal with thinking-mode behavior
at all: it's a direct-answer captioning model, not a reasoning model, so
none of the thinking-leak issue below would apply to it in the first place.
"""

import base64
import os
import subprocess
from pathlib import Path

from openai import OpenAI

VISION_MODEL = os.environ.get("VISION_LLM_MODEL", "accounts/fireworks/models/kimi-k2p6").strip('\"\' ')

CAPTION_SYSTEM_PROMPT = """You are describing a single film frame for a spatial
audio placement agent that has never seen the footage. Describe only what is
visually present: setting, lighting, camera framing, character position and
action, and any visible directional cues (e.g. something happening to the
left/right of frame, a light source, an object in motion). Do not describe
dialogue, sound, or music -- those come from a separate audio analysis stage.

Respond with ONLY the 1-2 sentence description itself. Do not restate these
instructions, do not include any preamble or lead-in phrase such as "Looking
at the image" or "Let me analyze", and do not show your reasoning. Output
only the final descriptive sentences, present tense, factual."""

# Defense-in-depth: even with thinking disabled, Kimi K2 deployments don't
# always reliably suppress chain-of-thought in message.content (documented
# behavior across the Kimi K2 family, not specific to this one model
# string). If a lead-in phrase still shows up, keep only what follows it.
_LEAD_IN_MARKERS = [
    "looking at the image",
    "looking at this image",
    "let me analyze the image",
    "let me look at the image",
    "let's analyze the image",
    "analyzing the image",
]


def _strip_reasoning_preamble(raw_text):
    lowered = raw_text.lower()
    best_idx = -1
    best_marker = None
    for marker in _LEAD_IN_MARKERS:
        idx = lowered.rfind(marker)
        if idx > best_idx:
            best_idx = idx
            best_marker = marker

    if best_idx == -1:
        return raw_text.strip()

    after = raw_text[best_idx + len(best_marker):]
    return after.lstrip(":\n- ").strip()


def _get_duration_sec(video_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


def extract_keyframe(video_path, out_path, timestamp=None):
    """
    Grabs one representative frame from video_path. Defaults to the clip's
    midpoint; falls back to 1.0s if duration can't be read (e.g. corrupt
    or unusually short file).
    """
    video_path = Path(video_path)
    out_path = Path(out_path)

    if timestamp is None:
        try:
            timestamp = _get_duration_sec(video_path) / 2
        except Exception:
            timestamp = 1.0

    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video_path),
         "-frames:v", "1", "-q:v", "2", str(out_path)],
        capture_output=True, check=True
    )
    return out_path


def caption_scene(frame_path, model=None):
    """
    Sends a single keyframe to the vision-language model and returns a
    short visual caption, ready to drop into the placement agent's
    visual_caption field.
    """
    client = OpenAI(
        api_key=os.environ.get("VISION_LLM_API_KEY", "EMPTY"),
        base_url=os.environ.get("VISION_LLM_BASE_URL", "https://api.fireworks.ai/inference/v1")
    )

    b64_image = base64.b64encode(Path(frame_path).read_bytes()).decode("utf-8")

    response = client.chat.completions.create(
        model=model or VISION_MODEL,
        messages=[
            {"role": "system", "content": CAPTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
                    {"type": "text", "text": "Describe this frame."}
                ]
            }
        ],
        temperature=0.2,
        max_tokens=500,
        # Kimi K2.6 is a thinking model by default, and Fireworks doesn't
        # route the reasoning trace to a separate field the way Moonshot's
        # own API does -- it can leak straight into message.content. This
        # is what was eating the token budget before the model ever reached
        # the actual description, causing every caption to truncate mid-word.
        extra_body={"thinking": {"type": "disabled"}},
    )

    choice = response.choices[0]
    raw = (choice.message.content or "").strip()

    if choice.finish_reason == "length":
        print(f"[caption_extractor] WARNING: response truncated at max_tokens for {frame_path}")

    if not raw:
        # Some Kimi/Fireworks deployments still return empty content even
        # with thinking disabled, if reasoning consumed the whole budget.
        reasoning = getattr(choice.message, "reasoning_content", None) or getattr(choice.message, "reasoning", None)
        print(f"[caption_extractor] WARNING: empty content for {frame_path}; reasoning present: {bool(reasoning)}")
        return ""

    return _strip_reasoning_preamble(raw)


def auto_caption_scene(video_path, workdir):
    """
    Convenience wrapper: video_path -> keyframe -> caption, in one call.
    workdir is where the extracted keyframe .jpg gets written (kept, not
    deleted, so you can spot-check what the model actually saw).
    """
    workdir = Path(workdir)
    workdir.mkdir(exist_ok=True, parents=True)
    frame_path = workdir / f"{Path(video_path).stem}_keyframe.jpg"

    extract_keyframe(video_path, frame_path)
    return caption_scene(frame_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python caption_extractor.py <video_path>")
        sys.exit(1)

    caption = auto_caption_scene(sys.argv[1], workdir="output/keyframes")
    print(caption)
