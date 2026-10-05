from __future__ import annotations

import unittest
from datetime import datetime

from app.sensor_node import make_detection_event


class DetectionEventTests(unittest.TestCase):
    def test_payload_has_traceable_synthetic_provenance(self):
        event = make_detection_event("C2", "anaquel-01-zona-1", 1, 4)
        self.assertEqual(event["device_id"], "C2")
        self.assertEqual(event["zone_id"], "anaquel-01-zona-1")
        self.assertTrue(event["synthetic"])
        self.assertEqual(event["source"], "mqtt_simulator_not_camera_model")
        datetime.fromisoformat(str(event["observed_at_utc"]).replace("Z", "+00:00"))

    def test_empty_state_transition_is_deterministic(self):
        before = make_detection_event("C2", "zone-1", 3, 4)
        after = make_detection_event("C2", "zone-1", 4, 4)
        self.assertFalse(before["shelf_empty"])
        self.assertTrue(after["shelf_empty"])

    def test_zero_empty_after_means_no_stockout_event(self):
        event = make_detection_event("C4", "zone-3", 100, 0)
        self.assertFalse(event["shelf_empty"])


if __name__ == "__main__":
    unittest.main()
