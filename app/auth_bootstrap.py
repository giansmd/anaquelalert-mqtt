from __future__ import annotations

import csv
import os
import re
import tempfile
from pathlib import Path

USERNAME_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
MIN_PASSWORD_LENGTH = 24


def write_bootstrap_users_file(
    directory: str | Path,
    clients: dict[str, str],
    *,
    owner_uid: int | None = None,
    owner_gid: int | None = None,
) -> Path:
    if not clients:
        raise ValueError("At least one MQTT user is required")

    for username, password in clients.items():
        if not USERNAME_PATTERN.fullmatch(username):
            raise ValueError("MQTT username contains unsupported characters")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError("MQTT password must contain at least 24 characters")
        if "\n" in password or "\r" in password:
            raise ValueError("MQTT password must not contain a line break")

    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "users.csv"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=output_dir,
            prefix=".users-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(["user_id", "password", "is_superuser"])
            for username, password in sorted(clients.items()):
                writer.writerow([username, password, "false"])
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, 0o600)
        if owner_uid is not None or owner_gid is not None:
            current = temp_path.stat()
            os.chown(
                temp_path,
                current.st_uid if owner_uid is None else owner_uid,
                current.st_gid if owner_gid is None else owner_gid,
            )
        os.replace(temp_path, target)
        return target
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main() -> None:
    names = ("C2", "C3", "C4", "INGESTOR")
    clients: dict[str, str] = {}
    usernames: set[str] = set()
    for name in names:
        username = os.getenv(f"MQTT_{name}_USERNAME", "")
        password = os.getenv(f"MQTT_{name}_PASSWORD", "")
        if username in usernames:
            raise SystemExit("MQTT usernames must be unique")
        usernames.add(username)
        clients[username] = password

    try:
        path = write_bootstrap_users_file(
            os.getenv("MQTT_BOOTSTRAP_DIR", "/bootstrap"),
            clients,
            owner_uid=int(os.getenv("EMQX_UID", "1000")),
            owner_gid=int(os.getenv("EMQX_GID", "1000")),
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(f"MQTT bootstrap failed: {exc}") from exc

    print(f"MQTT bootstrap file ready: {path}", flush=True)


if __name__ == "__main__":
    main()
