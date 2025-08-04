-- Temperature Checker Database Schema

-- Table to store application configuration and window state
CREATE TABLE IF NOT EXISTS app_state (
    id INTEGER PRIMARY KEY,
    window_state TEXT NOT NULL CHECK(window_state IN ('open', 'closed')),
    mode TEXT NOT NULL CHECK(mode IN ('heating', 'cooling')),
    last_notification_type TEXT CHECK(last_notification_type IN ('open_windows', 'close_windows', NULL)),
    last_notification_time DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table to store temperature readings and forecast data
CREATE TABLE IF NOT EXISTS temperature_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    current_temp REAL NOT NULL,
    daily_high_forecast REAL,
    daily_low_forecast REAL,
    zip_code TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table to track notifications sent
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    notification_type TEXT NOT NULL CHECK(notification_type IN ('open_windows', 'close_windows')),
    current_temp REAL NOT NULL,
    forecast_high REAL,
    forecast_low REAL,
    message TEXT NOT NULL,
    sent_successfully BOOLEAN NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert default app state
INSERT OR IGNORE INTO app_state (id, window_state, mode) 
VALUES (1, 'closed', 'cooling');

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_temp_readings_timestamp ON temperature_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_notifications_timestamp ON notifications(timestamp);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(notification_type);