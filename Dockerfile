# syntax=docker/dockerfile:1

# PyCoral 2.0.0 provides CPython 3.9 ARM64 wheels. Keep its runtime together.
FROM python:3.9-slim-bookworm@sha256:a02e9c5406c416c504d6c9a1a306ff4080c3173f1008d192f953bd20382a2d5c AS detector
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/data/radar.db
WORKDIR /app
RUN test "$(uname -m)" = aarch64 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        curl libusb-1.0-0 libstdc++6 libglib2.0-0 tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-detector.txt .
RUN python -m pip install --no-cache-dir -r requirements-detector.txt
RUN curl -fL https://raw.githubusercontent.com/google-coral/pycoral/v2.0.0/libedgetpu_bin/direct/aarch64/libedgetpu.so.1.0 \
        -o /usr/local/lib/libedgetpu.so.1.0 \
    && echo 'd35192f5541d68688f4c050d634b2a5619680d42b3d9362adfedd5a1b54d3888  /usr/local/lib/libedgetpu.so.1.0' | sha256sum -c - \
    && ln -s libedgetpu.so.1.0 /usr/local/lib/libedgetpu.so.1 \
    && ldconfig
RUN mkdir -p models /data \
    && curl -fL https://raw.githubusercontent.com/google-coral/test_data/104342d2d3480b3e66203073dac24f4e2dbb4c41/ssd_mobilenet_v2_coco_quant_postprocess_edgetpu.tflite -o models/detector.tflite \
    && curl -fL https://raw.githubusercontent.com/google-coral/test_data/104342d2d3480b3e66203073dac24f4e2dbb4c41/coco_labels.txt -o models/coco_labels.txt \
    && echo 'b94e2d58222c32f31062c7604e10488e2aba9259ab77462039476a3ba4597fef  models/detector.tflite' | sha256sum -c - \
    && echo 'dc183f003fc753c4c43fae6fdf7f387559449573f13fa32e517fb7453fd380f1  models/coco_labels.txt' | sha256sum -c -
# Catch missing native libraries during image construction, without claiming TPU access.
RUN python -c "import ctypes, cv2, pytesseract, tweepy; from pycoral.adapters import common, detect; from pycoral.utils.edgetpu import list_edge_tpus; ctypes.CDLL('libedgetpu.so.1')" \
    && tesseract --version
COPY app.py config.py ocr.py posting.py storage.py tracker.py ./
STOPSIGNAL SIGINT
CMD ["python", "app.py"]

# The web UI has no dependency on the older Coral Python runtime.
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS dashboard
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/data/radar.db
WORKDIR /app
COPY requirements-dashboard.txt .
RUN python -m pip install --no-cache-dir -r requirements-dashboard.txt \
    && mkdir -p /data
COPY server.py config.py storage.py ./
COPY templates/ templates/
COPY static/ static/
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "2", "--access-logfile", "-", "--error-logfile", "-", "server:app"]
