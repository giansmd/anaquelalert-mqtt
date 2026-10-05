from __future__ import annotations

import argparse
import json
import os
import time
from threading import Event

import paho.mqtt.client as mqtt


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor MQTT de eventos AnaquelAlert")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--duration", type=float, default=20)
    args = parser.parse_args()
    connected = Event()
    received = 0
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="anaquelalert-monitor",
        protocol=mqtt.MQTTv311,
    )

    def on_connect(mqtt_client, _userdata, _flags, reason_code, _properties):
        if reason_code == 0:
            mqtt_client.subscribe("anaquelalert/demo/#", qos=1)
            connected.set()
        else:
            print(f"CONNECT_FAILED {reason_code}", flush=True)

    def on_message(_client, _userdata, message):
        nonlocal received
        received += 1
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except json.JSONDecodeError:
            payload = message.payload.decode("utf-8", errors="replace")
        print(json.dumps({"topic": message.topic, "qos": message.qos, "retained": message.retain, "payload": payload}, ensure_ascii=False), flush=True)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.host, args.port, keepalive=20)
    client.loop_start()
    if not connected.wait(10):
        client.loop_stop()
        return 2
    deadline = time.monotonic() + args.duration
    try:
        while time.monotonic() < deadline:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    client.disconnect()
    client.loop_stop()
    print(f"MONITOR_DONE received={received}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
