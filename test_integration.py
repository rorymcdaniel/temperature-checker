#!/usr/bin/env python3
"""
Integration tests for Temperature Checker application
"""

import pytest
import os
import tempfile
from unittest.mock import patch, Mock
from datetime import datetime

from temp_checker import TemperatureChecker, DatabaseAdapter, WeatherData, Config


class TestIntegration:
    """Integration tests using real database and minimal mocking"""
    
    def setup_method(self):
        """Setup test environment with temporary database"""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # Create test configuration
        self.test_config = Config(
            db_path=self.temp_db_path,
            zip_code='10001',
            telegram_token='test_token',
            telegram_chat_id='test_chat_id',
            close_windows_temp=78.0,
            open_windows_temp=76.0,
            forecast_high_threshold=80.0,
            heating_close_temp=55.0,
            heating_open_temp=65.0,
            heating_forecast_low_threshold=70.0,
            quiet_start_hour=22,
            quiet_start_minute=30,
            quiet_end_hour=7,
            quiet_end_minute=0,
            default_mode='cooling'
        )
        
        # Initialize real database with schema
        self.database = DatabaseAdapter(self.temp_db_path)
        self._init_test_schema()
    
    def teardown_method(self):
        """Cleanup temporary database"""
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)
    
    def _init_test_schema(self):
        """Initialize test database schema"""
        schema = """
        CREATE TABLE IF NOT EXISTS app_state (
            id INTEGER PRIMARY KEY,
            window_state TEXT NOT NULL CHECK(window_state IN ('open', 'closed')),
            mode TEXT NOT NULL CHECK(mode IN ('heating', 'cooling')),
            last_notification_type TEXT CHECK(last_notification_type IN ('open_windows', 'close_windows', NULL)),
            last_notification_time DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS temperature_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            current_temp REAL NOT NULL,
            daily_high_forecast REAL,
            daily_low_forecast REAL,
            zip_code TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
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
        
        INSERT OR IGNORE INTO app_state (id, window_state, mode) 
        VALUES (1, 'closed', 'cooling');
        """
        
        import sqlite3
        with sqlite3.connect(self.temp_db_path) as conn:
            conn.executescript(schema)
            conn.commit()
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_complete_cooling_close_windows_flow(self, mock_telegram, mock_weather):
        """Test complete flow for cooling mode close windows notification"""
        # Setup mocks
        mock_weather.return_value = WeatherData(78.0, 85.0, 65.0)  # Triggers close
        mock_telegram.return_value = True
        
        # Set initial state to windows open
        self.database.update_app_state(window_state='open')
        
        # Create checker and run
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        with patch.object(checker, 'is_quiet_hours', return_value=False):
            checker.check_and_notify()
        
        # Verify database state
        app_state = self.database.get_app_state()
        assert app_state.window_state == 'closed'
        assert app_state.last_notification_type == 'close_windows'
        assert app_state.last_notification_time is not None
        
        # Verify telegram was called
        mock_telegram.assert_called_once()
        message = mock_telegram.call_args[0][0]
        assert '🌡️' in message
        assert 'Close Windows' in message
        assert '78.0°F' in message
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_complete_cooling_open_windows_flow(self, mock_telegram, mock_weather):
        """Test complete flow for cooling mode open windows notification"""
        # Setup mocks
        mock_weather.return_value = WeatherData(75.0, 85.0, 65.0)  # Triggers open
        mock_telegram.return_value = True
        
        # Set initial state to windows closed
        self.database.update_app_state(window_state='closed')
        
        # Create checker and run
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        with patch.object(checker, 'is_quiet_hours', return_value=False):
            checker.check_and_notify()
        
        # Verify database state
        app_state = self.database.get_app_state()
        assert app_state.window_state == 'open'
        assert app_state.last_notification_type == 'open_windows'
        
        # Verify telegram was called
        mock_telegram.assert_called_once()
        message = mock_telegram.call_args[0][0]
        assert '🌬️' in message
        assert 'Open Windows' in message
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_complete_heating_close_windows_flow(self, mock_telegram, mock_weather):
        """Test complete flow for heating mode close windows notification"""
        # Setup mocks
        mock_weather.return_value = WeatherData(50.0, 60.0, 40.0)  # Triggers close
        mock_telegram.return_value = True
        
        # Set initial state for heating mode, windows open
        self.database.update_app_state(window_state='open', mode='heating')
        
        # Create checker and run
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        with patch.object(checker, 'is_quiet_hours', return_value=False):
            checker.check_and_notify()
        
        # Verify database state
        app_state = self.database.get_app_state()
        assert app_state.window_state == 'closed'
        assert app_state.last_notification_type == 'close_windows'
        assert app_state.mode == 'heating'
        
        # Verify telegram was called with heating message
        mock_telegram.assert_called_once()
        message = mock_telegram.call_args[0][0]
        assert '🥶' in message
        assert 'heat' in message
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_complete_heating_open_windows_flow(self, mock_telegram, mock_weather):
        """Test complete flow for heating mode open windows notification"""
        # Setup mocks
        mock_weather.return_value = WeatherData(68.0, 65.0, 50.0)  # Triggers open
        mock_telegram.return_value = True
        
        # Set initial state for heating mode, windows closed
        self.database.update_app_state(window_state='closed', mode='heating')
        
        # Create checker and run
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        with patch.object(checker, 'is_quiet_hours', return_value=False):
            checker.check_and_notify()
        
        # Verify database state
        app_state = self.database.get_app_state()
        assert app_state.window_state == 'open'
        assert app_state.last_notification_type == 'open_windows'
        assert app_state.mode == 'heating'
        
        # Verify telegram was called with heating message
        mock_telegram.assert_called_once()
        message = mock_telegram.call_args[0][0]
        assert '☀️' in message
        assert 'warm' in message
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_temperature_recording(self, mock_telegram, mock_weather):
        """Test that temperature data is properly recorded"""
        # Setup mocks
        weather_data = WeatherData(77.0, 84.0, 66.0)
        mock_weather.return_value = weather_data
        mock_telegram.return_value = True
        
        # Create checker and run
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        checker.check_and_notify()
        
        # Verify temperature was recorded
        import sqlite3
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.execute("""
                SELECT current_temp, daily_high_forecast, daily_low_forecast, zip_code
                FROM temperature_readings ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == 77.0
            assert row[1] == 84.0
            assert row[2] == 66.0
            assert row[3] == '10001'
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_notification_recording_success(self, mock_telegram, mock_weather):
        """Test that successful notifications are properly recorded"""
        # Setup mocks
        mock_weather.return_value = WeatherData(78.0, 85.0, 65.0)
        mock_telegram.return_value = True
        
        # Set state to trigger notification
        self.database.update_app_state(window_state='open')
        
        # Create checker and run
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        with patch.object(checker, 'is_quiet_hours', return_value=False):
            checker.check_and_notify()
        
        # Verify notification was recorded
        import sqlite3
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.execute("""
                SELECT notification_type, current_temp, sent_successfully, message
                FROM notifications ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == 'close_windows'
            assert row[1] == 78.0
            assert row[2] == 1  # True
            assert '🌡️' in row[3]
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_notification_recording_failure(self, mock_telegram, mock_weather):
        """Test that failed notifications are properly recorded"""
        # Setup mocks
        mock_weather.return_value = WeatherData(78.0, 85.0, 65.0)
        mock_telegram.return_value = False  # Simulate failure
        
        # Set state to trigger notification
        self.database.update_app_state(window_state='open')
        
        # Create checker and run
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        with patch.object(checker, 'is_quiet_hours', return_value=False):
            checker.check_and_notify()
        
        # Verify notification failure was recorded
        import sqlite3
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.execute("""
                SELECT notification_type, sent_successfully
                FROM notifications ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == 'close_windows'
            assert row[1] == 0  # False
        
        # Verify app state was NOT updated on failure
        app_state = self.database.get_app_state()
        assert app_state.window_state == 'open'  # Should remain open
        assert app_state.last_notification_type is None
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_quiet_hours_blocking(self, mock_telegram, mock_weather):
        """Test that notifications are blocked during quiet hours"""
        # Setup mocks
        mock_weather.return_value = WeatherData(78.0, 85.0, 65.0)
        mock_telegram.return_value = True
        
        # Set state to trigger notification
        self.database.update_app_state(window_state='open')
        
        # Create checker and run during quiet hours
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        with patch.object(checker, 'is_quiet_hours', return_value=True):
            checker.check_and_notify()
        
        # Verify no notification was sent
        mock_telegram.assert_not_called()
        
        # Verify app state unchanged
        app_state = self.database.get_app_state()
        assert app_state.window_state == 'open'
        assert app_state.last_notification_type is None
        
        # Verify temperature was still recorded
        import sqlite3
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM temperature_readings")
            count = cursor.fetchone()[0]
            assert count > 0
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_duplicate_notification_blocking(self, mock_telegram, mock_weather):
        """Test that duplicate notifications within 30 minutes are blocked"""
        # Setup mocks
        mock_weather.return_value = WeatherData(78.0, 85.0, 65.0)
        mock_telegram.return_value = True
        
        # Set state with recent notification
        recent_time = datetime(2023, 1, 1, 10, 0, 0)
        self.database.update_app_state(
            window_state='open',
            last_notification_type='close_windows'
        )
        
        # Manually set notification time to recent
        import sqlite3
        with sqlite3.connect(self.temp_db_path) as conn:
            conn.execute("""
                UPDATE app_state 
                SET last_notification_time = ? 
                WHERE id = 1
            """, (recent_time.isoformat(),))
            conn.commit()
        
        # Create checker and run 15 minutes later
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        current_time = datetime(2023, 1, 1, 10, 15, 0)  # 15 minutes later
        with patch.object(checker, 'is_quiet_hours', return_value=False):
            with patch.object(checker.time_provider, 'now', return_value=current_time):
                checker.check_and_notify()
        
        # Verify no notification was sent due to recent duplicate
        mock_telegram.assert_not_called()
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    def test_no_weather_data_handling(self, mock_weather):
        """Test handling when weather data is unavailable"""
        # Setup mock to return None
        mock_weather.return_value = None
        
        # Create checker and run
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        # Should complete without error
        checker.check_and_notify()
        
        # Verify no temperature was recorded
        import sqlite3
        with sqlite3.connect(self.temp_db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM temperature_readings")
            count = cursor.fetchone()[0]
            assert count == 0
    
    @patch('temp_checker.WeatherAdapter.fetch_weather_data')
    @patch('temp_checker.TelegramAdapter.send_message')
    def test_mode_switching_persistence(self, mock_telegram, mock_weather):
        """Test that mode changes persist and affect logic correctly"""
        # Setup for cooling mode first
        mock_weather.return_value = WeatherData(78.0, 85.0, 65.0)
        mock_telegram.return_value = True
        
        self.database.update_app_state(window_state='open', mode='cooling')
        
        checker = TemperatureChecker(
            database=self.database,
            config=self.test_config
        )
        
        with patch.object(checker, 'is_quiet_hours', return_value=False):
            checker.check_and_notify()
        
        # Verify cooling logic was used
        mock_telegram.assert_called_once()
        message = mock_telegram.call_args[0][0]
        assert '🌡️' in message  # Cooling emoji
        
        # Reset mocks
        mock_telegram.reset_mock()
        
        # Switch to heating mode with cold temperature
        mock_weather.return_value = WeatherData(50.0, 60.0, 40.0)
        self.database.update_app_state(window_state='open', mode='heating')
        
        # Reset the notification state so a new notification can be sent
        import sqlite3
        with sqlite3.connect(self.temp_db_path) as conn:
            conn.execute("""
                UPDATE app_state 
                SET last_notification_type = NULL, last_notification_time = NULL
                WHERE id = 1
            """)
            conn.commit()
        
        with patch.object(checker, 'is_quiet_hours', return_value=False):
            checker.check_and_notify()
        
        # Verify heating logic was used
        mock_telegram.assert_called_once()
        message = mock_telegram.call_args[0][0]
        assert '🥶' in message  # Heating emoji


if __name__ == "__main__":
    pytest.main([__file__, "-v"])