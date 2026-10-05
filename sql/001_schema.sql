CREATE DATABASE IF NOT EXISTS anaquelalert CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE anaquelalert;

CREATE TABLE IF NOT EXISTS devices (
    device_id VARCHAR(64) PRIMARY KEY,
    zone_id VARCHAR(128) NOT NULL,
    availability ENUM('online', 'offline', 'unknown') NOT NULL DEFAULT 'unknown',
    last_seen_utc DATETIME(6) NULL,
    updated_at_utc DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX idx_devices_zone (zone_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS detection_events (
    event_id CHAR(36) PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    zone_id VARCHAR(128) NOT NULL,
    observed_at_utc DATETIME(6) NOT NULL,
    shelf_empty BOOLEAN NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    synthetic BOOLEAN NOT NULL DEFAULT TRUE,
    payload_json JSON NOT NULL,
    received_at_utc DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_detection_device FOREIGN KEY (device_id)
        REFERENCES devices(device_id),
    INDEX idx_detection_zone_time (zone_id, observed_at_utc),
    INDEX idx_detection_device_time (device_id, observed_at_utc)
) ENGINE=InnoDB;
