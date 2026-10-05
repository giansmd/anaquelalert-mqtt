import csv
import stat
import tempfile
import unittest
from pathlib import Path

from app.auth_bootstrap import write_bootstrap_users_file


class AuthBootstrapTests(unittest.TestCase):
    def test_writes_each_client_as_non_superuser_and_restricts_file_mode(self):
        clients = {"aa-c2": "x" * 32, "aa-ingestor": "y" * 32}
        with tempfile.TemporaryDirectory() as tmp:
            path = write_bootstrap_users_file(tmp, clients)
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["user_id"] for row in rows], ["aa-c2", "aa-ingestor"])
            self.assertEqual([row["is_superuser"] for row in rows], ["false", "false"])
            self.assertEqual(rows[0]["password"], "x" * 32)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_rejects_password_shorter_than_24_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "24 characters"):
                write_bootstrap_users_file(tmp, {"aa-c2": "short"})

    def test_rejects_usernames_outside_safe_charset(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "username"):
                write_bootstrap_users_file(tmp, {"bad,user": "x" * 32})

    def test_rejects_newlines_in_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "line break"):
                write_bootstrap_users_file(tmp, {"aa-c2": "x" * 31 + "\n"})


if __name__ == "__main__":
    unittest.main()
