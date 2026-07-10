FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (ffmpeg is required for audio processing)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    libgl1 \
    libglib2.0-0 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Install all dependencies together with the CPU index URL to prevent 
# pip from pulling incompatible ABI versions of torch/torchaudio
RUN pip3 install --no-cache-dir \
    torch torchaudio torchcodec \
    demucs \
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
    gradio \
    fastapi \
    uvicorn \
    python-multipart \
    pyjwt \
    cryptography \
    boto3 \
    --extra-index-url https://download.pytorch.org/whl/cpu

COPY . /app

# Pre-download spaudiopy HRIR FABIAN dataset to avoid stalling the first user request
RUN python3 -c "from binaural_renderer import get_hrirs; get_hrirs(prefer_real=True)"

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
