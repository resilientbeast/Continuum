"""
caption_extractor.py

Automatic replacement for hand-authored visual_caption. Extracts a
representative keyframe from each scene's source video clip via ffmpeg,
then captions it using a self-hosted vision-language model (e.g.
Qwen2.5-VL-7B-Instruct) served through vLLM on the same OpenAI-compatible
API surface as placement_agent_harness.py's reasoning model.

Requires: ffmpeg + ffprobe on PATH (already in the project Dockerfile),
a running `vllm serve <VL model> --port <VISION_PORT>` instance.

Env vars (separate from the main LLM_* vars, since this is a different
model on a different port):
  VISION_LLM_BASE_URL   e.g. http://localhost:8001/v1
  VISION_LLM_API_KEY    "EMPTY" is fine for a local vLLM server
  VISION_LLM_MODEL      default: Qwen/Qwen2.5-VL-7B-Instruct
"""

import base64
import os
import subprocess
from pathlib import Path

from openai import OpenAI

VISION_MODEL = os.environ.get("VISION_LLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")

CAPTION_SYSTEM_PROMPT = """You are describing a single film frame for a spatial
audio placement agent that has never seen the footage. Describe only what is
visually present: setting, lighting, camera framing, character position and
action, and any visible directional cues (e.g. something happening to the
left/right of frame, a light source, an object in motion). Do not describe
dialogue, sound, or music -- those come from a separate audio analysis stage.
Keep it to 1-2 sentences, present tense, factual."""


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
    Sends a single keyframe to the self-hosted VL model and returns a
    short visual caption, ready to drop into the placement agent's
    visual_caption field.
    """
    client = OpenAI(
        api_key=os.environ.get("VISION_LLM_API_KEY", "EMPTY"),
        base_url=os.environ.get("VISION_LLM_BASE_URL")
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
        max_tokens=120
    )

    return response.choices[0].message.content.strip()


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
