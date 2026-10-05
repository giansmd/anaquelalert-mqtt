from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from threading import Event
from uuid import uuid4

import paho.mqtt.client as mqtt


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise SystemExit(f"{name} debe ser entero") from exc


def make_detection_event(node_id: str, zone_id: str, sequence: int, empty_after: int) -> dict[str, object]:
    """Genera una observación determinista y explícitamente sintética."""
    confidence_cycle = (0.93, 0.88, 0.95, 0.91)
    return {
        "event_id": str(uuid4()),
        "device_id": node_id,
        "zone_id": zone_id,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "sequence": sequence,
        "event_type": "shelf_detection",
        "shelf_empty": bool(empty_after > 0 and sequence >= empty_after),
        "confidence": confidence_cycle[(sequence - 1) % len(confidence_cycle)],
        "synthetic": True,
        "source": "mqtt_simulator_not_camera_model",
    }


def main() -> int:
    node_id = os.getenv("NODE_ID", "C2")
    zone_id = os.getenv("ZONE_ID", "anaquel-01-zona-1")
    host = os.getenv("MQTT_HOST", "127.0.0.1")
    port = env_int("MQTT_PORT", 1883)
    keepalive = env_int("KEEPALIVE_SECONDS", 5)
    interval = float(os.getenv("INTERVAL_SECONDS", "2"))
    empty_after = env_int("EMPTY_AFTER", 4)
    crash_after = env_int("CRASH_AFTER", 0)
    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")

    event_topic = f"anaquelalert/demo/zones/{zone_id}/detections"
    availability_topic = f"anaquelalert/demo/nodes/{node_id}/availability"
    connected = Event()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"anaquelalert-{node_id}",
        protocol=mqtt.MQTTv311,
        clean_session=True,
    )
    if username:
        client.username_pw_set(username, password or "")

    will_payload = json.dumps({"device_id": node_id, "zone_id": zone_id, "status": "offline", "synthetic": True})
    client.will_set(availability_topic, will_payload, qos=1, retain=True)

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        if reason_code == 0:
            connected.set()
        else:
            print(f"CONNECT_FAILED node={node_id} reason={reason_code}", flush=True)

    client.on_connect = on_connect

    try:
        client.connect(host, port, keepalive=keepalive)
        client.loop_start()
    except OSError as exc:
        print(f"BROKER_UNAVAILABLE host={host}:{port} error={exc}", file=sys.stderr, flush=True)
        return 2

    if not connected.wait(timeout=10):
        client.loop_stop()
        return 3

    online = json.dumps({"device_id": node_id, "zone_id": zone_id, "status": "online", "synthetic": True})
    client.publish(availability_topic, online, qos=1, retain=True).wait_for_publish(timeout=3)
    time.sleep(1.0)  # permite que el ingestor se suscriba antes de la primera lectura

    sequence = 0
    try:
        while True:
            sequence += 1
            event = make_detection_event(node_id, zone_id, sequence, empty_after)
            info = client.publish(event_topic, json.dumps(event), qos=1, retain=False)
            info.wait_for_publish(timeout=3)
            print(json.dumps({"topic": event_topic, "event": event}, ensure_ascii=False), flush=True)

            if crash_after and sequence >= crash_after:
                # Terminación abrupta intencional para que el broker pruebe el LWT.
                print(f"SIMULATED_ABRUPT_EXIT node={node_id} after={sequence}", flush=True)
                sys.stdout.flush()
                os._exit(86)
            time.sleep(interval)
    except KeyboardInterrupt:
        offline = json.dumps({"device_id": node_id, "zone_id": zone_id, "status": "offline", "synthetic": True, "reason": "graceful_shutdown"})
        client.publish(availability_topic, offline, qos=1, retain=True).wait_for_publish(timeout=3)
        client.disconnect()
        client.loop_stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
