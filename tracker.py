"""Conservative centroid tracking with time-interpolated road gates."""
from collections import Counter
from dataclasses import dataclass, field
from math import hypot

MPH_PER_MPS = 2.2369362921


@dataclass
class Detection:
    x: float
    y: float
    bbox: tuple
    kind: str = "car"


@dataclass
class Track:
    id: int
    detection: Detection
    seen_at: float
    direction: int = 0
    gates: dict = field(default_factory=dict)
    speed: float = None
    elapsed: float = None
    invalid: bool = False
    plate_votes: Counter = field(default_factory=Counter)
    last_ocr: float = float("-inf")

    def plate(self, min_votes):
        if not self.plate_votes:
            return None, 0
        plate, votes = self.plate_votes.most_common(1)[0]
        if votes < min_votes or list(self.plate_votes.values()).count(votes) > 1:
            return None, votes
        return plate, votes


def crossing_time(x0, x1, t0, t1, gate):
    if t1 <= t0 or x1 == x0:
        return None
    fraction = (gate - x0) / (x1 - x0)
    if 0 <= fraction <= 1:
        return t0 + fraction * (t1 - t0)
    return None


class Tracker:
    def __init__(self, gate_a, gate_b, distance_m, min_seconds=0.12,
                 max_seconds=4.0, max_match=150, timeout=0.8):
        if not (gate_a < gate_b and distance_m > 0):
            raise ValueError("Invalid gate configuration")
        self.gates = {"a": gate_a, "b": gate_b}
        self.distance_m = distance_m
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self.max_match = max_match
        self.timeout = timeout
        self.tracks = {}
        self.next_id = 1

    def _event(self, tr, required_votes):
        if tr.invalid or tr.speed is None:
            return None
        plate, votes = tr.plate(required_votes)
        return {"track_id": tr.id, "vehicle_type": tr.detection.kind,
                "plate": plate, "plate_votes": votes, "speed_mph": tr.speed,
                "elapsed_seconds": tr.elapsed,
                "direction": "right" if tr.direction > 0 else "left"}

    def update(self, detections, timestamp, required_votes=2):
        events = []
        for tid, tr in list(self.tracks.items()):
            if timestamp - tr.seen_at > self.timeout:
                event = self._event(tr, required_votes)
                if event:
                    events.append(event)
                del self.tracks[tid]
        possible = []
        for tid, tr in self.tracks.items():
            for i, d in enumerate(detections):
                if d.kind != tr.detection.kind:
                    continue
                distance = hypot(d.x - tr.detection.x, d.y - tr.detection.y)
                if distance <= self.max_match:
                    possible.append((distance, tid, i))
        # If association is ambiguous, invalidate instead of assigning a plate/speed.
        ambiguous_tracks, ambiguous_detections = set(), set()
        margin = max(8, self.max_match * 0.12)
        for idx, (dist, tid, i) in enumerate(possible):
            for dist2, tid2, j in possible[idx + 1:]:
                if tid == tid2 and i != j and abs(dist - dist2) <= margin:
                    ambiguous_tracks.add(tid)
                    ambiguous_detections.update((i, j))
                if i == j and tid != tid2 and abs(dist - dist2) <= margin:
                    ambiguous_tracks.update((tid, tid2))
                    ambiguous_detections.add(i)
        for tid in ambiguous_tracks:
            self.tracks[tid].invalid = True

        used_tracks, used_detections, matched = set(), set(), []
        for _, tid, i in sorted(possible):
            if tid in used_tracks or i in used_detections:
                continue
            if tid in ambiguous_tracks or i in ambiguous_detections:
                continue
            tr, d = self.tracks[tid], detections[i]
            used_tracks.add(tid)
            used_detections.add(i)
            dx = d.x - tr.detection.x
            direction = 1 if dx > 3 else -1 if dx < -3 else 0
            if direction and tr.direction and direction != tr.direction:
                tr.invalid = True
            if direction and not tr.direction:
                tr.direction = direction
            if not tr.invalid and tr.speed is None and direction == tr.direction != 0:
                for label, gate in self.gates.items():
                    hit = crossing_time(tr.detection.x, d.x, tr.seen_at,
                                        timestamp, gate)
                    if hit is not None and label not in tr.gates:
                        tr.gates[label] = hit
                if len(tr.gates) == 2:
                    seconds = abs(tr.gates["b"] - tr.gates["a"])
                    consistent = (tr.gates["b"] > tr.gates["a"]) == (tr.direction > 0)
                    if consistent and self.min_seconds <= seconds <= self.max_seconds:
                        tr.speed = round(self.distance_m / seconds * MPH_PER_MPS, 1)
                        tr.elapsed = round(seconds, 4)
                    else:
                        tr.invalid = True
            tr.detection, tr.seen_at = d, timestamp
            matched.append((tr, d))

        for i, d in enumerate(detections):
            if i not in used_detections and i not in ambiguous_detections:
                tr = Track(self.next_id, d, timestamp)
                self.tracks[tr.id] = tr
                self.next_id += 1
                matched.append((tr, d))
        return matched, events

    def flush(self, required_votes=2):
        events = [self._event(tr, required_votes) for tr in self.tracks.values()]
        self.tracks.clear()
        return [event for event in events if event]
