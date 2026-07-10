FROM rocm/pytorch:latest
WORKDIR /app
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*
# ROCm torch FIRST. `pip install demucs` also pulls a generic PyPI torch;
# installing it after this line risks pip seeing torch as "already
# satisfied" and silently skipping the ROCm build, leaving
# torch.cuda.is_available() == False with no error. Installing ROCm torch
# first, then demucs with --no-deps, avoids that failure mode entirely.
RUN pip3 install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/rocm7.2
RUN pip3 install --no-cache-dir --no-deps demucs
RUN pip3 install --no-cache-dir \
    scenedetect[opencv] \
    openai \
    anthropic \
    pydub \
    numpy \
    scipy \
    librosa \
    soundfile \
    ear \
    spaudiopy \
    gradio
COPY . /app
# NOTE: no HSA_OVERRIDE_GFX_VERSION or PYTORCH_ROCM_ARCH here on purpose.
# HSA_OVERRIDE_GFX_VERSION exists to spoof an UNSUPPORTED consumer GPU as
# a supported ISA - MI300X (gfx942) is already a first-class supported
# ROCm target, so setting this can misroute kernels
# (hipErrorNoBinaryForGPU) or cause perf regressions. PYTORCH_ROCM_ARCH is
# a build-from-source flag with no effect on the prebuilt pip wheel above.
# If you ever build PyTorch from source instead, that's the only case
# where PYTORCH_ROCM_ARCH=gfx942 belongs back in this file.
#
# ENTRYPOINT, not CMD: main.py requires --input-video and supports --only
# for resumable per-stage runs (see main.py's own docstring, which
# recommends running `--only segment,separate` first). A bare
# `CMD ["python3", "main.py"]` would exit immediately on argparse's
# required-argument error. Pass args after the image name, e.g.:
#   docker run ... atmos-coherence-agent --input-video scenes/source_film.mp4 --output-dir output
ENTRYPOINT ["python3", "main.py"]
