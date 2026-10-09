# Coral Speed Radar

Traffic observation prototype for the **Google Coral Dev Board** (Mendel Linux). No Raspberry Pi required.

**What it does:** Edge TPU SSD MobileNet vehicle detection; time-interpolated dual-gate speed estimation; CPU-based plate candidate extraction + Tesseract OCR; persistent SQLite records; auto-refreshing Flask dashboard; optional X/Twitter posts with plate and estimated speed. Default mode logs locally without posting.

**This is a prototype, not a calibrated or certified speed radar.** A vehicle detector does not itself detect license plates. This system's heuristic plate localizer and simple centroid tracker may make mistakes. Publicly posted guesses can misattribute a speed to an innocent driver: verify OCR and speed with controlled footage before enabling X.

## Docker deployment on the Coral Dev Board

Use a 64-bit Mendel installation with working camera and Edge TPU drivers,
Docker Engine, and Docker Compose v2 or newer. Check the host before building:

```sh
uname -m                     # must be aarch64
docker version              # both client and server must respond
docker compose version
ls -l /dev/apex_0 /dev/video0
```

Mendel uses an older Debian base; a current Docker installer may not support it.
Use an Engine version compatible with the board's existing kernel. The container
supplies user-space libraries; camera and TPU kernel drivers run on the host.
Most USB UVC cameras work through `/dev/video0`. CSI cameras can require a
device-specific GStreamer pipeline that this app does not yet supply.

The detector image uses Google's released PyCoral 2.0.0 and TensorFlow Lite
2.5.0.post1 ARM64 wheels, with the matching `libedgetpu` library. Runtime and model
downloads are pinned and checksum-verified, and the build does not depend on the
Coral apt repository. Python 3.9 is required by these released wheels and is now
past end of life. PyCoral and libedgetpu are archived: this is a frozen legacy
software stack. The dashboard runs separately
on Python 3.12 with Flask and Gunicorn.

```sh
git clone https://github.com/cmc0619/coral_speed_radar.git
cd coral_speed_radar
cp .env.example .env
# Edit .env: CAMERA_DEVICE, frame dimensions, gates and measured gate distance.
docker compose build
docker compose up -d
docker compose logs -f detector
```

Both services run as native ARM64 processes on the board. Compose maps only
`CAMERA_DEVICE` (default `/dev/video0`) and `TPU_DEVICE` (default `/dev/apex_0`) into
the detector. Keep `CAMERA_SOURCE=0` to read the mapped `/dev/video0` inside the
container. It does not use privileged mode or CPU emulation on the board.
The detection model and labels are included in the image. Compose sets their
paths and fixes the database path to `/data/radar.db`; the `radar-data` volume
persists across container replacements. `.env` is excluded from image builds,
and only the detector receives X credentials.

The dashboard defaults to `http://127.0.0.1:8080` on the board. To view from a
trusted LAN, set `DASHBOARD_HOST=0.0.0.0` in `.env` and recreate the dashboard.
`DASHBOARD_PORT` selects the host port. The dashboard has no authentication or
TLS; keep it off the public internet.

```sh
docker compose ps
docker compose logs --tail=100
docker compose up -d --build       # rebuild and replace services after an update
docker compose down               # stop services; keep recorded data
```

The restart policy starts services after a Docker daemon restart unless they
were explicitly stopped. Enable the Docker daemon at boot on the board.
The detector receives SIGINT on shutdown, allowing its existing cleanup code to
flush completed tracks, with a 60-second grace period. A stuck camera capture
loop can still leave the process alive; the restart policy does not fix that.
OCR and X publication still run synchronously in the detection loop.

### Switching an existing native installation

Stop the old processes before starting Compose so only one detector owns the
camera. If the previous systemd examples were enabled:

```sh
sudo systemctl disable --now coral-speed-radar.service coral-speed-radar-dashboard.service
```

To import an existing `radar.db`, stop its writer, then copy it into the volume
before starting either container:

```sh
docker compose create dashboard
docker compose cp radar.db dashboard:/data/radar.db
docker compose up -d
```

Back up the original database before switching. `docker compose down --volumes`
deletes the recorded data; ordinary `down` preserves it.

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
docker compose build
docker run --rm -v "$PWD/tests:/app/tests:ro" coral-speed-radar-detector:local \
  python -m unittest discover -s tests -v
python3 tests/smoke_docker.py
```

The smoke test starts only a dashboard, writes an event from the detector image,
and verifies that HTTP responses retain it after container recreation. It removes
only its own temporary Compose project and volume, using a randomly assigned
localhost port to avoid interfering with a running dashboard.

GitHub Actions builds and tests both images on a native ARM64 runner. These are
packaging and software checks. Even a passing ARM64 build does not prove that
Docker runs on Mendel, that the host devices work, or that capture and inference
meet the timing needed for reliable tracking. On the board, verify TPU inference,
camera capture, OCR, and processed-frame intervals under traffic before relying
on the measurements. Compare the same workload with native execution to measure
container overhead. Hardware performance has not been established by CI.
