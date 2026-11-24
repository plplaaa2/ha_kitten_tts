FROM python:3.11-slim-bookworm

ENV HF_HOME=/data/huggingface \
    PYTHONUNBUFFERED=1 \
    ORT_DISABLE_TELEMETRY=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libsndfile1 espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# KittenML declares Torch even when the selected model runs through ONNX.
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.11.0+cpu" "torchaudio==2.11.0+cpu" \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check

COPY server.py .
EXPOSE 10500/tcp
CMD ["python", "server.py", "--host", "0.0.0.0"]
