# Build
docker build -t continuum-coherence-agent .

# Build
docker build -t continuum-coherence-agent .

# Args go AFTER the image name now (main.py requires --input-video; there's
# no default CMD to fall back on). Per main.py's own docstring, run Stage 2
# (Demucs) in isolation first, since it's the one stage not verified
# end-to-end in the sandbox this was built in:

docker run -it \
  -e LLM_BASE_URL="${LLM_BASE_URL:-https://api.fireworks.ai/inference/v1}" \
  -e LLM_API_KEY="${LLM_API_KEY}" \
  -e LLM_MODEL="${LLM_MODEL:-accounts/fireworks/models/gemma-2-9b-it}" \
  -e VISION_LLM_BASE_URL="${VISION_LLM_BASE_URL:-https://api.fireworks.ai/inference/v1}" \
  -e VISION_LLM_API_KEY="${VISION_LLM_API_KEY}" \
  -e VISION_LLM_MODEL="${VISION_LLM_MODEL:-accounts/fireworks/models/firellava-13b}" \
  -v $(pwd)/scenes:/app/scenes \
  -v $(pwd)/output:/app/output \
  continuum-coherence-agent \
  --input-video scenes/source_film.mp4 --output-dir output --only segment,separate

# Once that's confirmed working, run the full pipeline:
#
# docker run ... continuum-coherence-agent \
#   --input-video scenes/source_film.mp4 --output-dir output --launch-dashboard
