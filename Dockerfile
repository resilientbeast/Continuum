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
    gradio \
    fastapi \
    uvicorn \
    python-multipart \
    pyjwt \
    cryptography \
    boto3
COPY . /app
# We now run the FastAPI app by default
EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
