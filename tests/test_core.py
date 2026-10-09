import os
import tempfile
import unittest

from tracker import Detection, Tracker, Track, crossing_time
from ocr import normalize_plate
from storage import initialize, save_event, recent, update_status


def detect(x):
    return Detection(x, 100, (x - 20, 80, x + 20, 120))


class TrackingTests(unittest.TestCase):
    def test_crossing(self):
        self.assertAlmostEqual(crossing_time(100, 200, 1, 2, 150), 1.5)
        self.assertIsNone(crossing_time(100, 110, 1, 2, 150))

    def test_speed_and_plate(self):
        tracker = Tracker(200, 400, 10, max_match=120, timeout=2)
        for n, x in enumerate((100, 190, 280, 370, 460)):
            pairs, events = tracker.update([detect(x)], float(n))
            self.assertFalse(events)
            pairs[0][0].plate_votes["ABC123"] += 1
        events = tracker.flush()
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]["speed_mph"], 10.1, places=1)
        self.assertEqual(events[0]["plate"], "ABC123")
        self.assertEqual(events[0]["direction"], "right")

    def test_leftward(self):
        tracker = Tracker(200, 400, 10, max_match=170, timeout=2)
        for n, x in enumerate((500, 350, 250, 150)):
            tracker.update([detect(x)], float(n))
        self.assertEqual(tracker.flush()[0]["direction"], "left")

    def test_no_first_gate(self):
        tracker = Tracker(200, 400, 10, max_match=200)
        tracker.update([detect(300)], 0)
        tracker.update([detect(440)], 1)
        self.assertFalse(tracker.flush())

    def test_ocr_tie_rejected(self):
        track = Track(1, detect(100), 0)
        track.plate_votes.update({"ABC123": 2, "ABC128": 2})
        self.assertIsNone(track.plate(2)[0])

    def test_normalization(self):
        self.assertEqual(normalize_plate("abc-123"), "ABC123")
        self.assertIsNone(normalize_plate("??"))

    def test_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            db=os.path.join(directory, "radar.db")
            initialize(db)
            event={"track_id": 1, "plate": "ABC123", "plate_votes": 2,
                   "vehicle_type": "car", "speed_mph": 25.0,
                   "direction": "right", "elapsed_seconds": .4}
            id_=save_event(db,event,"offline")
            update_status(db,id_,"published")
            self.assertEqual(recent(db)[0]["post_status"],"published")


if __name__=="__main__":
    unittest.main()
