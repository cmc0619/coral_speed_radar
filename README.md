# Coral Speed Radar

Traffic observation prototype for the **Google Coral Dev Board** (Mendel Linux). No Raspberry Pi required.

**What it does:** Edge TPU SSD MobileNet vehicle detection; time-interpolated dual-gate speed estimation; CPU-based plate candidate extraction + Tesseract OCR; persistent SQLite records; auto-refreshing Flask dashboard; optional X/Twitter posts with plate and estimated speed. Default mode logs locally without posting.

**This is a prototype, not a calibrated or certified speed radar.** A vehicle detector does not itself detect license plates. This system's heuristic plate localizer and simple centroid tracker may make mistakes. Publicly posted guesses can misattribute a speed to an innocent driver: verify OCR and speed with controlled footage before enabling X.

## Install on the Coral Dev Board

Use the board's compatible **Mendel Linux** image and Debian packages (do not force recent pip TensorFlow/YOLO/PyTorch packages onto its system Python):

```sh
sudo apt update
sudo apt install python3-pycoral python3-opencv python3-flask python3-numpy \
  python3-pytesseract tesseract-ocr curl
# Optional X access (check compatibility with your board's Python):
python3 -m pip install --user 'tweepy<5'
```

The apt package names/versions available depend on your Mendel image. Verify with `apt-cache policy python3-pycoral python3-pytesseract` and install compatible equivalents if necessary. Most regular USB UVC cameras are exposed as `/dev/video0`. CSI cameras can require a device-specific GStreamer pipeline that this starter doesn't yet supply.

Get Google's TPU-compiled detection model and COCO label file:

```sh
mkdir -p models
curl -fL https://raw.githubusercontent.com/google-coral/test_data/master/ssd_mobilenet_v2_coco_quant_postprocess_edgetpu.tflite -o models/detector.tflite
curl -fL https://raw.githubusercontent.com/google-coral/test_data/master/coco_labels.txt -o models/coco_labels.txt
```

## Configure and run

```sh
cp .env.example .env
# Edit .env: CAMERA_SOURCE, frame dimensions, both gate coordinates and real-world distance.
set -a; . ./.env; set +a
python3 app.py
# Second shell: export the same .env then start:
python3 server.py
```

Dashboard defaults to `http://127.0.0.1:8080` on the board. To view from another machine on a **trusted LAN**, set `DASHBOARD_HOST=0.0.0.0`; Flask's development server has no authentication or TLS, so do not expose it to the internet.

## Calibrating speed

Position a **stationary camera broadside to a single lane**. Gates `GATE_A_X` and `GATE_B_X` are vertical lines in camera-image pixels, not lengths on the road. `GATE_DISTANCE_METERS` is the measured *distance along the travel path*, at that lane, between the gate positions. The speed estimate is:

```
mph = gate_distance_meters / elapsed_gate_seconds * 2.2369362921
```

The app linearly interpolates between camera capture timestamps when a vehicle's bounding-box center crosses each gate. It uses the latest available frame from a capture thread to avoid stale queued frames. It is still sensitive to lens perspective, variable bounding boxes, driver lane position, camera shutter, and vehicle overlap. Verify using independently measured reference speeds and physical dimensions. For multiple lanes, use camera homography and a stronger MOT tracker (e.g., ByteTrack) before expecting meaningful accuracy.

## Plate reading

The Edge TPU detects cars/trucks/buses/motorcycles. OpenCV searches inside vehicle crops for plate-like rectangles, then Tesseract attempts OCR. Only plates with `OCR_MIN_VOTES` matching reads are accepted; otherwise the dashboard shows `UNKNOWN`. This heuristic will miss or misread plates under many real conditions. A dedicated quantized Edge TPU plate detector should eventually replace it.

## X/Twitter

Set `POST_MODE=x` in `.env` and provide `X_CONSUMER_KEY`, `X_CONSUMER_SECRET`, `X_ACCESS_TOKEN`, and `X_ACCESS_TOKEN_SECRET`. The app uses Tweepy v2 `Client.create_tweet`. Your X app must have write authorization and adequate API entitlement. A failed post is retained locally and marked `failed` (no automatic retry); unknown plate readings are not posted. Never commit `.env` or credentials.

## Testing

```sh
python3 -m compileall -q .
python3 -m unittest discover -s tests -v
```

GitHub Actions checks syntax and hardware-independent tracker/database behavior. It cannot validate the Edge TPU runtime, camera capture, plate OCR on traffic, speed accuracy, or X API entitlement. Live hardware testing is still required.
