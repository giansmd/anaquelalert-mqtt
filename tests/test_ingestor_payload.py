import json
import unittest

from app.ingestor import decode_payload


class IngestorPayloadTests(unittest.TestCase):
    def test_decodes_json_object(self):
        payload = decode_payload(b'{"device_id":"C2"}')
        self.assertEqual(payload, {"device_id": "C2"})

    def test_rejects_json_array(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            decode_payload(b'[1, 2]')

    def test_rejects_json_scalar(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            decode_payload(b'"not-an-object"')

    def test_invalid_json_still_raises_decode_error(self):
        with self.assertRaises(json.JSONDecodeError):
            decode_payload(b'{bad json}')


if __name__ == "__main__":
    unittest.main()
