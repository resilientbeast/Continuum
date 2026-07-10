# Build
docker build -t atmos-coherence-agent .

# --network=host: the container needs to reach the two vllm serve processes
# running on the notebook host (reasoning model on :8000, vision model on
# :8001). Simplest option on a single-user Linux notebook.
#
# Args go AFTER the image name now (main.py requires --input-video; there's
# no default CMD to fall back on). Per main.py's own docstring, run Stage 2
# (Demucs) in isolation first, since it's the one stage not verified
# end-to-end in the sandbox this was built in:

docker run -it --cap-add=SYS_PTRACE --security-opt seccomp=unconfined \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  --ipc=host --shm-size 8G \
  --network=host \
  -e LLM_BASE_URL="${LLM_BASE_URL:-http://localhost:8000/v1}" \
  -e LLM_API_KEY="${LLM_API_KEY:-not-needed-for-local-vllm}" \
  -e LLM_MODEL="${LLM_MODEL:-Qwen/Qwen2.5-32B-Instruct}" \
  -e VISION_LLM_BASE_URL="${VISION_LLM_BASE_URL:-http://localhost:8001/v1}" \
  -e VISION_LLM_API_KEY="${VISION_LLM_API_KEY:-EMPTY}" \
  -e VISION_LLM_MODEL="${VISION_LLM_MODEL:-Qwen/Qwen2.5-VL-7B-Instruct}" \
  -v $(pwd)/scenes:/app/scenes \
  -v $(pwd)/output:/app/output \
  atmos-coherence-agent \
  --input-video scenes/source_film.mp4 --output-dir output --only segment,separate

# Once that's confirmed working, run the full pipeline:
#
# docker run ... atmos-coherence-agent \
#   --input-video scenes/source_film.mp4 --output-dir output --launch-dashboard
