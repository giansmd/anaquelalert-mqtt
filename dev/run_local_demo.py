from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
AMQTT = Path(PYTHON).with_name("amqtt")


def wait_for_port(timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 1883), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError("AMQTT no abrió 127.0.0.1:1883")


def main() -> int:
    if not AMQTT.exists():
        raise SystemExit("Falta amqtt; instalar dev/requirements-dev.txt en el entorno virtual")

    broker = subprocess.Popen(
        [str(AMQTT), "-c", str(ROOT / "dev" / "amqtt-broker.yaml")],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    monitor = None
    nodes: dict[str, subprocess.Popen] = {}
    outputs: dict[str, str] = {}
    try:
        wait_for_port()
        base_env = os.environ.copy()
        base_env.update({
            "PYTHONPATH": str(ROOT),
            "MQTT_HOST": "127.0.0.1",
            "MQTT_PORT": "1883",
            "INTERVAL_SECONDS": "0.25",
            "KEEPALIVE_SECONDS": "5",
        })
        monitor = subprocess.Popen(
            [PYTHON, "-m", "app.monitor", "--duration", "6"],
            cwd=ROOT,
            env=base_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        time.sleep(0.4)

        for node, zone, empty_after, crash_after in (
            ("C2", "anaquel-01-zona-1", "4", "0"),
            ("C3", "anaquel-01-zona-2", "3", "3"),
            ("C4", "anaquel-01-zona-3", "0", "0"),
        ):
            env = base_env.copy()
            env.update({
                "NODE_ID": node,
                "ZONE_ID": zone,
                "EMPTY_AFTER": empty_after,
                "CRASH_AFTER": crash_after,
            })
            nodes[node] = subprocess.Popen(
                [PYTHON, "-m", "app.sensor_node"],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

        time.sleep(3.0)
        for node in ("C2", "C4"):
            if nodes[node].poll() is None:
                nodes[node].send_signal(signal.SIGINT)
        for node, process in nodes.items():
            outputs[node] = process.communicate(timeout=4)[0]
        monitor_output = monitor.communicate(timeout=10)[0] if monitor else ""

        detected_events = Counter()
        availability = set()
        for line in monitor_output.splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = record.get("payload", {})
            if record.get("topic", "").endswith("/detections"):
                detected_events[payload.get("device_id", "?")] += 1
            if record.get("topic", "").endswith("/availability"):
                availability.add((payload.get("device_id"), payload.get("status")))

        if not all(detected_events[node] > 0 for node in ("C2", "C3", "C4")):
            raise RuntimeError(f"No se recibieron eventos de todos los nodos: {dict(detected_events)}")
        if ("C3", "offline") not in availability:
            raise RuntimeError("El broker local no entregó el LWT offline de C3")
        if nodes["C3"].returncode != 86:
            raise RuntimeError(f"C3 debía terminar abruptamente (86), devolvió {nodes['C3'].returncode}")

        print("Demostración MQTT local completada (broker de desarrollo AMQTT; no es EMQX):")
        print(f"- eventos recibidos: {dict(detected_events)}")
        print("- disponibilidad C3: online → offline (LWT recibido)")
        print("- QoS usado por los nodos: 1")
        print("- payloads: sintéticos; no son inferencias de una cámara ni resultados de campo")
        return 0
    finally:
        for node, process in nodes.items():
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
        if monitor and monitor.poll() is None:
            monitor.terminate()
            monitor.wait(timeout=3)
        if broker.poll() is None:
            broker.terminate()
            try:
                broker.wait(timeout=3)
            except subprocess.TimeoutExpired:
                broker.kill()


if __name__ == "__main__":
    raise SystemExit(main())
