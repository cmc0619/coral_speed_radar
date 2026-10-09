"""Google Coral Dev Board vehicle/speed/plate detector process."""
import logging
import threading
import time
from pathlib import Path

from config import Config
from ocr import read_plate
from posting import post_to_x
from storage import initialize, save_event, update_status
from tracker import Detection, Tracker

LOG = logging.getLogger("radar")
VEHICLES = {"car", "bus", "truck", "motorcycle"}


class Camera:
    """Capture continuously; inference always processes the newest camera frame."""
    def __init__(self, source, width, height):
        import cv2
        source = int(source) if str(source).isdigit() else source
        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            raise RuntimeError("Camera did not open: {!r}".format(source))
        self.running, self.sequence = True, 0
        self.frame, self.time = None, None
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.capture, daemon=True)
        self.thread.start()

    def capture(self):
        while self.running:
            ok, frame = self.cap.read()
            at = time.monotonic()
            if not ok:
                time.sleep(0.05)
                continue
            with self.lock:
                self.sequence += 1
                self.frame, self.time = frame, at

    def latest(self, seen):
        with self.lock:
            if self.frame is None or self.sequence == seen:
                return None
            return self.sequence, self.frame.copy(), self.time

    def close(self):
        self.running = False
        self.thread.join(timeout=1)
        self.cap.release()


def deliver(config, events):
    for event in events:
        status = ("offline" if config.post_mode == "offline" else
                  "pending" if event["plate"] else "skipped_no_consensus")
        event_id = save_event(config.database_path, event, status)
        LOG.info("event=%d plate=%s mph=%.1f votes=%d", event_id,
                 event["plate"] or "UNKNOWN", event["speed_mph"], event["plate_votes"])
        if status == "pending":
            try:
                result = post_to_x(event)
                update_status(config.database_path, event_id, "published")
                LOG.info("X post: %s", result)
            except Exception as exc:
                update_status(config.database_path, event_id, "failed", str(exc)[:500])
                LOG.exception("X post failed; event saved locally")


def main():
    import cv2
    from pycoral.adapters import common, detect
    from pycoral.utils.dataset import read_label_file
    from pycoral.utils.edgetpu import make_interpreter

    cfg = Config().validate()
    for path in (cfg.model_path, cfg.labels_path):
        if not Path(path).is_file():
            raise FileNotFoundError(path)
    labels = read_label_file(cfg.labels_path)
    interpreter = make_interpreter(cfg.model_path)
    interpreter.allocate_tensors()
    model_w, model_h = common.input_size(interpreter)
    tracker = Tracker(cfg.gate_a_x, cfg.gate_b_x, cfg.gate_distance_meters,
                      cfg.min_gate_seconds, cfg.max_gate_seconds,
                      cfg.max_match_pixels, cfg.track_timeout_seconds)
    initialize(cfg.database_path)
    camera = Camera(cfg.camera_source, cfg.frame_width, cfg.frame_height)
    LOG.info("Camera active. Mode=%s, gate spacing=%.2f m",
             cfg.post_mode, cfg.gate_distance_meters)
    sequence, checked, ocr_available = 0, False, True
    try:
        while True:
            shot = camera.latest(sequence)
            if shot is None:
                time.sleep(0.005)
                continue
            sequence, frame, captured_at = shot
            height, width = frame.shape[:2]
            if not checked:
                checked = True
                if (width, height) != (cfg.frame_width, cfg.frame_height):
                    raise RuntimeError("Camera resolution differs from configuration")
            resized = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                                 (model_w, model_h))
            common.set_input(interpreter, resized)
            interpreter.invoke()
            objects = detect.get_objects(interpreter, cfg.detection_confidence)
            observations = []
            for obj in objects:
                kind = labels.get(obj.id, "").lower()
                if kind not in VEHICLES:
                    continue
                b = obj.bbox
                box = (max(0, b.xmin * width / model_w),
                       max(0, b.ymin * height / model_h),
                       min(width, b.xmax * width / model_w),
                       min(height, b.ymax * height / model_h))
                if box[2] - box[0] < 25 or box[3] - box[1] < 25:
                    continue
                observations.append(Detection((box[0] + box[2]) / 2,
                                              (box[1] + box[3]) / 2, box, kind))
            matches, events = tracker.update(observations, captured_at,
                                             cfg.ocr_min_votes)
            deliver(cfg, events)
            if ocr_available:
                for tr, d in matches:
                    if tr.invalid or captured_at - tr.last_ocr < cfg.ocr_interval_seconds:
                        continue
                    tr.last_ocr = captured_at
                    try:
                        candidate = read_plate(frame, d.bbox, cfg.ocr_min_confidence)
                    except Exception as error:
                        LOG.warning("Disabling OCR because of error: %s", error)
                        ocr_available = False
                        break
                    if candidate:
                        tr.plate_votes[candidate[0]] += 1
    except KeyboardInterrupt:
        LOG.info("Stopped")
    finally:
        deliver(cfg, tracker.flush(cfg.ocr_min_votes))
        camera.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    main()
