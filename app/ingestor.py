from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

import mysql.connector
import paho.mqtt.client as mqtt


def connect_database():
    delay = 1
    while True:
        try:
            return mysql.connector.connect(
                host=os.getenv("MYSQL_HOST", "mysql"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                database=os.getenv("MYSQL_DATABASE", "anaquelalert"),
                user=os.getenv("MYSQL_USER", "anaquel"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                connection_timeout=5,
                autocommit=True,
            )
        except mysql.connector.Error as exc:
            print(f"MYSQL_WAIT error={exc} retry_seconds={delay}", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 15)


def parse_mysql_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def main() -> None:
    db = connect_database()
    cursor = db.cursor()
    host = os.getenv("MQTT_HOST", "emqx")
    port = int(os.getenv("MQTT_PORT", "1883"))
    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="anaquelalert-mysql-ingestor",
        protocol=mqtt.MQTTv311,
        clean_session=True,
    )
    if username:
        client.username_pw_set(username, password or "")

    def on_connect(mqtt_client, _userdata, _flags, reason_code, _properties):
        if reason_code == 0:
            mqtt_client.subscribe("anaquelalert/demo/#", qos=1)
            Path("/tmp/ingestor-ready").touch()
            print("MQTT_SUBSCRIBED topic=anaquelalert/demo/# qos=1", flush=True)
        else:
            Path("/tmp/ingestor-ready").unlink(missing_ok=True)
            print(f"MQTT_CONNECT_FAILED reason={reason_code}", flush=True)

    def on_disconnect(_client, _userdata, _disconnect_flags, _reason_code, _properties):
        Path("/tmp/ingestor-ready").unlink(missing_ok=True)

    def on_message(_client, _userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if message.topic.endswith("/availability"):
                cursor.execute(
                    """INSERT INTO devices (device_id, zone_id, availability, last_seen_utc)
                       VALUES (%s, %s, %s, UTC_TIMESTAMP(6))
                       ON DUPLICATE KEY UPDATE zone_id=VALUES(zone_id),
                         availability=VALUES(availability), last_seen_utc=UTC_TIMESTAMP(6)""",
                    (payload["device_id"], payload["zone_id"], payload["status"]),
                )
                print(f"DB_DEVICE status={payload['status']} device={payload['device_id']}", flush=True)
                return

            if message.topic.endswith("/detections"):
                event_at = parse_mysql_utc(payload["observed_at_utc"])
                cursor.execute(
                    """INSERT IGNORE INTO devices (device_id, zone_id, availability, last_seen_utc)
                       VALUES (%s, %s, 'unknown', UTC_TIMESTAMP(6))""",
                    (payload["device_id"], payload["zone_id"]),
                )
                cursor.execute(
                    """INSERT IGNORE INTO detection_events
                       (event_id, device_id, zone_id, observed_at_utc, shelf_empty,
                        confidence, synthetic, payload_json)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, CAST(%s AS JSON))""",
                    (
                        payload["event_id"], payload["device_id"], payload["zone_id"],
                        event_at, payload["shelf_empty"], payload["confidence"],
                        payload["synthetic"], json.dumps(payload),
                    ),
                )
                print(f"DB_EVENT device={payload['device_id']} zone={payload['zone_id']} empty={payload['shelf_empty']}", flush=True)
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            print(f"INVALID_MESSAGE topic={message.topic} error={exc}", flush=True)
        except mysql.connector.Error as exc:
            print(f"MYSQL_WRITE_ERROR error={exc}", flush=True)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    delay = 1
    while True:
        try:
            print(f"MQTT_CONNECT host={host}:{port}", flush=True)
            client.connect(host, port, keepalive=30)
            client.loop_forever(retry_first_connection=True)
        except OSError as exc:
            print(f"MQTT_WAIT error={exc} retry_seconds={delay}", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 15)
        except KeyboardInterrupt:
            break
    cursor.close()
    db.close()


if __name__ == "__main__":
    main()
