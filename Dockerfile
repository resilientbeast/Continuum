FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (ffmpeg is required for audio processing)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first to keep image size small and prevent CUDA/ROCm bloat
RUN pip3 install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install demucs and other dependencies
RUN pip3 install --no-cache-dir \
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
    boto3

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
