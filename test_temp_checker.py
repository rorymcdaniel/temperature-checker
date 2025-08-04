#!/usr/bin/env python3
"""
Comprehensive test suite for Temperature Checker application
"""

import pytest
import sqlite3
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, time
from typing import Dict, Any

from temp_checker_refactored import (
    TemperatureChecker, DatabaseAdapter, WeatherAdapter, TelegramAdapter, TimeAdapter,
    AppState, WeatherData
)


@pytest.mark.skip(reason="Database functionality is tested in integration tests")
class TestDatabaseAdapter:
    """Test cases for DatabaseAdapter class"""
    
    def setup_method(self):
        """Setup test environment with in-memory database"""
        self.db_adapter = DatabaseAdapter(':memory:')
        # Create schema directly for tests (don't rely on external file)
        self._init_test_schema()
    
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
        with sqlite3.connect(self.db_adapter.db_path) as conn:
            conn.executescript(schema)
            conn.commit()
    
    def test_get_app_state_existing(self):
        """Test getting existing app state"""
        state = self.db_adapter.get_app_state()
        assert state.window_state == 'closed'
        assert state.mode == 'cooling'
        assert state.last_notification_type is None
        assert state.last_notification_time is None
    
    def test_get_app_state_default(self):
        """Test getting app state when none exists"""
        # Clear the default record
        with sqlite3.connect(self.db_adapter.db_path) as conn:
            conn.execute("DELETE FROM app_state WHERE id = 1")
            conn.commit()
        
        state = self.db_adapter.get_app_state('heating')
        assert state.window_state == 'closed'
        assert state.mode == 'heating'
        assert state.last_notification_type is None
        assert state.last_notification_time is None
    
    def test_update_app_state_window_only(self):
        """Test updating only window state"""
        self.db_adapter.update_app_state(window_state='open')
        state = self.db_adapter.get_app_state()
        assert state.window_state == 'open'
        assert state.mode == 'cooling'  # Should remain unchanged
    
    def test_update_app_state_mode_only(self):
        """Test updating only mode"""
        self.db_adapter.update_app_state(mode='heating')
        state = self.db_adapter.get_app_state()
        assert state.window_state == 'closed'  # Should remain unchanged
        assert state.mode == 'heating'
    
    def test_update_app_state_notification(self):
        """Test updating notification state"""
        self.db_adapter.update_app_state(last_notification_type='close_windows')
        state = self.db_adapter.get_app_state()
        assert state.last_notification_type == 'close_windows'
        assert state.last_notification_time is not None
    
    def test_record_temperature(self):
        """Test recording temperature data"""
        weather_data = WeatherData(current_temp=75.0, daily_high=85.0, daily_low=65.0)
        self.db_adapter.record_temperature(weather_data, '12345')
        
        with sqlite3.connect(self.db_adapter.db_path) as conn:
            cursor = conn.execute("""
                SELECT current_temp, daily_high_forecast, daily_low_forecast, zip_code
                FROM temperature_readings ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 75.0
            assert row[1] == 85.0
            assert row[2] == 65.0
            assert row[3] == '12345'
    
    def test_record_notification(self):
        """Test recording notification"""
        self.db_adapter.record_notification(
            'close_windows', 78.0, 85.0, 65.0, 'Test message', True
        )
        
        with sqlite3.connect(self.db_adapter.db_path) as conn:
            cursor = conn.execute("""
                SELECT notification_type, current_temp, message, sent_successfully
                FROM notifications ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 'close_windows'
            assert row[1] == 78.0
            assert row[2] == 'Test message'
            assert row[3] == 1  # True


class TestWeatherAdapter:
    """Test cases for WeatherAdapter class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.weather_adapter = WeatherAdapter()
    
    @patch('temp_checker_refactored.requests.get')
    def test_get_coordinates_from_zip_success(self, mock_get):
        """Test successful coordinate retrieval"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'places': [{'latitude': '40.7128', 'longitude': '-74.0060'}]
        }
        mock_get.return_value = mock_response
        
        lat, lon = self.weather_adapter.get_coordinates_from_zip('10001')
        assert lat == 40.7128
        assert lon == -74.0060
    
    @patch('temp_checker_refactored.requests.get')
    def test_get_coordinates_from_zip_failure(self, mock_get):
        """Test failed coordinate retrieval"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        lat, lon = self.weather_adapter.get_coordinates_from_zip('00000')
        assert lat == 0.0
        assert lon == 0.0
    
    @patch('temp_checker_refactored.requests.get')
    def test_get_coordinates_from_zip_exception(self, mock_get):
        """Test coordinate retrieval with exception"""
        mock_get.side_effect = Exception("Network error")
        
        lat, lon = self.weather_adapter.get_coordinates_from_zip('10001')
        assert lat == 0.0
        assert lon == 0.0
    
    @patch.object(WeatherAdapter, 'get_coordinates_from_zip')
    @patch('temp_checker_refactored.requests.get')
    def test_fetch_weather_data_success(self, mock_get, mock_coordinates):
        """Test successful weather data fetch"""
        mock_coordinates.return_value = (40.7128, -74.0060)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'current': {'temperature_2m': 75.0},
            'daily': {
                'temperature_2m_max': [85.0],
                'temperature_2m_min': [65.0]
            }
        }
        mock_get.return_value = mock_response
        
        weather_data = self.weather_adapter.fetch_weather_data('10001')
        assert weather_data is not None
        assert weather_data.current_temp == 75.0
        assert weather_data.daily_high == 85.0
        assert weather_data.daily_low == 65.0
    
    @patch.object(WeatherAdapter, 'get_coordinates_from_zip')
    def test_fetch_weather_data_no_coordinates(self, mock_coordinates):
        """Test weather data fetch with no coordinates"""
        mock_coordinates.return_value = (0.0, 0.0)
        
        weather_data = self.weather_adapter.fetch_weather_data('00000')
        assert weather_data is None
    
    def test_fetch_weather_data_no_zip(self):
        """Test weather data fetch with no ZIP code"""
        weather_data = self.weather_adapter.fetch_weather_data(None)
        assert weather_data is None
    
    @patch.object(WeatherAdapter, 'get_coordinates_from_zip')
    @patch('temp_checker_refactored.requests.get')
    def test_fetch_weather_data_api_error(self, mock_get, mock_coordinates):
        """Test weather data fetch with API error"""
        mock_coordinates.return_value = (40.7128, -74.0060)
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        weather_data = self.weather_adapter.fetch_weather_data('10001')
        assert weather_data is None


class TestTelegramAdapter:
    """Test cases for TelegramAdapter class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.telegram_adapter = TelegramAdapter()
    
    @patch('temp_checker_refactored.requests.post')
    def test_send_message_success(self, mock_post):
        """Test successful message sending"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        result = self.telegram_adapter.send_message(
            'Test message', 'test_token', 'test_chat_id'
        )
        assert result is True
    
    @patch('temp_checker_refactored.requests.post')
    def test_send_message_failure(self, mock_post):
        """Test failed message sending"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        result = self.telegram_adapter.send_message(
            'Test message', 'test_token', 'test_chat_id'
        )
        assert result is False
    
    def test_send_message_no_credentials(self):
        """Test sending message without credentials"""
        result = self.telegram_adapter.send_message('Test message', None, None)
        assert result is False
        
        result = self.telegram_adapter.send_message('Test message', 'token', None)
        assert result is False
    
    @patch('temp_checker_refactored.requests.post')
    def test_send_message_exception(self, mock_post):
        """Test sending message with exception"""
        mock_post.side_effect = Exception("Network error")
        
        result = self.telegram_adapter.send_message(
            'Test message', 'test_token', 'test_chat_id'
        )
        assert result is False


class TestTimeAdapter:
    """Test cases for TimeAdapter class"""
    
    def test_now(self):
        """Test getting current time"""
        time_adapter = TimeAdapter()
        now = time_adapter.now()
        assert isinstance(now, datetime)
        
        # Should be very close to actual now
        actual_now = datetime.now()
        diff = abs((now - actual_now).total_seconds())
        assert diff < 1.0  # Within 1 second


class TestTemperatureChecker:
    """Test cases for TemperatureChecker class"""
    
    def setup_method(self):
        """Setup test environment with mocked dependencies"""
        self.mock_database = Mock()
        self.mock_weather = Mock()
        self.mock_notification = Mock()
        self.mock_time = Mock()
        
        self.test_config = {
            'db_path': ':memory:',
            'zip_code': '10001',
            'telegram_token': 'test_token',
            'telegram_chat_id': 'test_chat_id',
            'close_windows_temp': 78.0,
            'open_windows_temp': 76.0,
            'forecast_high_threshold': 80.0,
            'heating_close_temp': 55.0,
            'heating_open_temp': 65.0,
            'heating_forecast_low_threshold': 70.0,
            'quiet_start_hour': 22,
            'quiet_start_minute': 30,
            'quiet_end_hour': 7,
            'quiet_end_minute': 0,
            'default_mode': 'cooling'
        }
        
        self.checker = TemperatureChecker(
            database=self.mock_database,
            weather=self.mock_weather,
            notification=self.mock_notification,
            time_provider=self.mock_time,
            config=self.test_config
        )
    
    def test_initialization_with_config(self):
        """Test initialization with provided config"""
        assert self.checker.config == self.test_config
        assert self.checker.database == self.mock_database
        assert self.checker.weather == self.mock_weather
    
    def test_is_quiet_hours_within_range(self):
        """Test quiet hours detection within range"""
        # Test time within quiet hours (11 PM)
        test_time = datetime(2023, 1, 1, 23, 0, 0)
        assert self.checker.is_quiet_hours(test_time) is True
        
        # Test time within quiet hours (6 AM)
        test_time = datetime(2023, 1, 1, 6, 0, 0)
        assert self.checker.is_quiet_hours(test_time) is True
    
    def test_is_quiet_hours_outside_range(self):
        """Test quiet hours detection outside range"""
        # Test time outside quiet hours (10 AM)
        test_time = datetime(2023, 1, 1, 10, 0, 0)
        assert self.checker.is_quiet_hours(test_time) is False
        
        # Test time outside quiet hours (8 PM)
        test_time = datetime(2023, 1, 1, 20, 0, 0)
        assert self.checker.is_quiet_hours(test_time) is False
    
    def test_is_quiet_hours_boundary(self):
        """Test quiet hours detection at boundaries"""
        # Test exact start time
        test_time = datetime(2023, 1, 1, 22, 30, 0)
        assert self.checker.is_quiet_hours(test_time) is True
        
        # Test exact end time
        test_time = datetime(2023, 1, 1, 7, 0, 0)
        assert self.checker.is_quiet_hours(test_time) is True
    
    def test_should_send_notification_quiet_hours(self):
        """Test notification blocking during quiet hours"""
        app_state = AppState('open', 'cooling', None, None)
        test_time = datetime(2023, 1, 1, 23, 0, 0)
        
        result = self.checker.should_send_notification('close_windows', app_state, test_time)
        assert result is False
    
    def test_should_send_notification_recent_duplicate(self):
        """Test notification blocking for recent duplicates"""
        recent_time = datetime(2023, 1, 1, 10, 0, 0)  # 15 minutes ago
        current_time = datetime(2023, 1, 1, 10, 15, 0)
        
        app_state = AppState('open', 'cooling', 'close_windows', recent_time)
        
        result = self.checker.should_send_notification('close_windows', app_state, current_time)
        assert result is False
    
    def test_should_send_notification_old_duplicate(self):
        """Test notification allowing for old duplicates"""
        old_time = datetime(2023, 1, 1, 9, 0, 0)  # 60 minutes ago
        current_time = datetime(2023, 1, 1, 10, 0, 0)
        
        app_state = AppState('open', 'cooling', 'close_windows', old_time)
        
        result = self.checker.should_send_notification('close_windows', app_state, current_time)
        assert result is True
    
    def test_should_send_notification_different_type(self):
        """Test notification allowing for different types"""
        recent_time = datetime(2023, 1, 1, 10, 0, 0)
        current_time = datetime(2023, 1, 1, 10, 15, 0)
        
        app_state = AppState('closed', 'cooling', 'close_windows', recent_time)
        
        result = self.checker.should_send_notification('open_windows', app_state, current_time)
        assert result is True
    
    def test_create_notification_message_cooling_close(self):
        """Test notification message creation for cooling close"""
        weather_data = WeatherData(78.0, 85.0, 65.0)
        message = self.checker.create_notification_message('close_windows', weather_data, 'cooling')
        
        assert '🌡️' in message
        assert 'Close Windows' in message
        assert '78.0°F' in message
        assert '85.0°F' in message
        assert 'AC' in message
    
    def test_create_notification_message_cooling_open(self):
        """Test notification message creation for cooling open"""
        weather_data = WeatherData(75.0, 85.0, 65.0)
        message = self.checker.create_notification_message('open_windows', weather_data, 'cooling')
        
        assert '🌬️' in message
        assert 'Open Windows' in message
        assert '75.0°F' in message
        assert 'fresh air' in message
    
    def test_create_notification_message_heating_close(self):
        """Test notification message creation for heating close"""
        weather_data = WeatherData(50.0, 60.0, 40.0)
        message = self.checker.create_notification_message('close_windows', weather_data, 'heating')
        
        assert '🥶' in message
        assert 'Close Windows' in message
        assert '50.0°F' in message
        assert 'heat' in message
    
    def test_create_notification_message_heating_open(self):
        """Test notification message creation for heating open"""
        weather_data = WeatherData(68.0, 70.0, 50.0)
        message = self.checker.create_notification_message('open_windows', weather_data, 'heating')
        
        assert '☀️' in message
        assert 'Open Windows' in message
        assert '68.0°F' in message
        assert 'warm' in message
    
    def test_check_cooling_mode_conditions_close_windows(self):
        """Test cooling mode conditions for closing windows"""
        weather_data = WeatherData(78.0, 85.0, 65.0)  # Hot enough and high forecast
        app_state = AppState('open', 'cooling', None, None)
        
        result = self.checker.check_cooling_mode_conditions(weather_data, app_state)
        assert result == 'close_windows'
    
    def test_check_cooling_mode_conditions_close_windows_no_forecast(self):
        """Test cooling mode conditions - no close due to low forecast"""
        weather_data = WeatherData(78.0, 75.0, 65.0)  # Hot enough but low forecast
        app_state = AppState('open', 'cooling', None, None)
        
        result = self.checker.check_cooling_mode_conditions(weather_data, app_state)
        assert result is None
    
    def test_check_cooling_mode_conditions_close_windows_already_closed(self):
        """Test cooling mode conditions - windows already closed"""
        weather_data = WeatherData(78.0, 85.0, 65.0)
        app_state = AppState('closed', 'cooling', None, None)
        
        result = self.checker.check_cooling_mode_conditions(weather_data, app_state)
        assert result is None
    
    def test_check_cooling_mode_conditions_open_windows(self):
        """Test cooling mode conditions for opening windows"""
        weather_data = WeatherData(75.0, 85.0, 65.0)  # Cool enough
        app_state = AppState('closed', 'cooling', None, None)
        
        result = self.checker.check_cooling_mode_conditions(weather_data, app_state)
        assert result == 'open_windows'
    
    def test_check_cooling_mode_conditions_open_windows_already_open(self):
        """Test cooling mode conditions - windows already open"""
        weather_data = WeatherData(75.0, 85.0, 65.0)
        app_state = AppState('open', 'cooling', None, None)
        
        result = self.checker.check_cooling_mode_conditions(weather_data, app_state)
        assert result is None
    
    def test_check_heating_mode_conditions_close_windows(self):
        """Test heating mode conditions for closing windows"""
        weather_data = WeatherData(50.0, 60.0, 40.0)  # Too cold
        app_state = AppState('open', 'heating', None, None)
        
        result = self.checker.check_heating_mode_conditions(weather_data, app_state)
        assert result == 'close_windows'
    
    def test_check_heating_mode_conditions_open_windows(self):
        """Test heating mode conditions for opening windows"""
        weather_data = WeatherData(68.0, 65.0, 50.0)  # Warm enough and low forecast
        app_state = AppState('closed', 'heating', None, None)
        
        result = self.checker.check_heating_mode_conditions(weather_data, app_state)
        assert result == 'open_windows'
    
    def test_check_heating_mode_conditions_open_windows_high_forecast(self):
        """Test heating mode conditions - no open due to high forecast"""
        weather_data = WeatherData(68.0, 80.0, 50.0)  # Warm enough but high forecast
        app_state = AppState('closed', 'heating', None, None)
        
        result = self.checker.check_heating_mode_conditions(weather_data, app_state)
        assert result is None
    
    def test_process_notification_success(self):
        """Test successful notification processing"""
        weather_data = WeatherData(78.0, 85.0, 65.0)
        app_state = AppState('open', 'cooling', None, None)
        
        self.mock_notification.send_message.return_value = True
        
        result = self.checker.process_notification('close_windows', weather_data, app_state)
        
        assert result is True
        self.mock_notification.send_message.assert_called_once()
        self.mock_database.record_notification.assert_called_once()
        self.mock_database.update_app_state.assert_called_once_with(
            window_state='closed', last_notification_type='close_windows'
        )
    
    def test_process_notification_failure(self):
        """Test failed notification processing"""
        weather_data = WeatherData(78.0, 85.0, 65.0)
        app_state = AppState('open', 'cooling', None, None)
        
        self.mock_notification.send_message.return_value = False
        
        result = self.checker.process_notification('close_windows', weather_data, app_state)
        
        assert result is False
        self.mock_notification.send_message.assert_called_once()
        self.mock_database.record_notification.assert_called_once()
        # Should not update app state on failure
        self.mock_database.update_app_state.assert_not_called()
    
    def test_check_and_notify_no_weather_data(self):
        """Test check_and_notify with no weather data"""
        self.mock_weather.fetch_weather_data.return_value = None
        
        self.checker.check_and_notify()
        
        self.mock_weather.fetch_weather_data.assert_called_once_with('10001')
        # Should not proceed further
        self.mock_database.record_temperature.assert_not_called()
    
    def test_check_and_notify_cooling_close_windows(self):
        """Test complete check_and_notify flow for cooling close windows"""
        weather_data = WeatherData(78.0, 85.0, 65.0)
        app_state = AppState('open', 'cooling', None, None)
        current_time = datetime(2023, 1, 1, 10, 0, 0)  # Not quiet hours
        
        self.mock_weather.fetch_weather_data.return_value = weather_data
        self.mock_database.get_app_state.return_value = app_state
        self.mock_time.now.return_value = current_time
        self.mock_notification.send_message.return_value = True
        
        self.checker.check_and_notify()
        
        # Verify all steps were called
        self.mock_weather.fetch_weather_data.assert_called_once()
        self.mock_database.record_temperature.assert_called_once()
        self.mock_database.get_app_state.assert_called_once()
        self.mock_notification.send_message.assert_called_once()
        self.mock_database.record_notification.assert_called_once()
        self.mock_database.update_app_state.assert_called_once()
    
    def test_check_and_notify_heating_mode(self):
        """Test check_and_notify with heating mode"""
        weather_data = WeatherData(50.0, 60.0, 40.0)
        app_state = AppState('open', 'heating', None, None)
        current_time = datetime(2023, 1, 1, 10, 0, 0)
        
        self.mock_weather.fetch_weather_data.return_value = weather_data
        self.mock_database.get_app_state.return_value = app_state
        self.mock_time.now.return_value = current_time
        self.mock_notification.send_message.return_value = True
        
        self.checker.check_and_notify()
        
        # Should process close_windows notification for heating mode
        self.mock_notification.send_message.assert_called_once()
        args, kwargs = self.mock_notification.send_message.call_args
        message = args[0]
        assert '🥶' in message
        assert 'Close Windows' in message
    
    def test_check_and_notify_no_notification_needed(self):
        """Test check_and_notify when no notification is needed"""
        weather_data = WeatherData(77.0, 85.0, 65.0)  # Temp too low for close_windows
        app_state = AppState('open', 'cooling', None, None)
        
        self.mock_weather.fetch_weather_data.return_value = weather_data
        self.mock_database.get_app_state.return_value = app_state
        
        self.checker.check_and_notify()
        
        # Should record temperature but not send notification
        self.mock_database.record_temperature.assert_called_once()
        self.mock_notification.send_message.assert_not_called()
    
    def test_check_and_notify_quiet_hours(self):
        """Test check_and_notify during quiet hours"""
        weather_data = WeatherData(78.0, 85.0, 65.0)
        app_state = AppState('open', 'cooling', None, None)
        current_time = datetime(2023, 1, 1, 23, 0, 0)  # Quiet hours
        
        self.mock_weather.fetch_weather_data.return_value = weather_data
        self.mock_database.get_app_state.return_value = app_state
        self.mock_time.now.return_value = current_time
        
        self.checker.check_and_notify()
        
        # Should record temperature but not send notification
        self.mock_database.record_temperature.assert_called_once()
        self.mock_notification.send_message.assert_not_called()


class TestMainFunction:
    """Test cases for the main function"""
    
    @patch('temp_checker_refactored.TemperatureChecker')
    def test_main_success(self, mock_checker_class):
        """Test successful main function execution"""
        mock_checker = Mock()
        mock_checker_class.return_value = mock_checker
        
        from temp_checker_refactored import main
        main()
        
        mock_checker_class.assert_called_once()
        mock_checker.check_and_notify.assert_called_once()
    
    @patch('temp_checker_refactored.TemperatureChecker')
    @patch('temp_checker_refactored.logger')
    def test_main_exception_handling(self, mock_logger, mock_checker_class):
        """Test main function exception handling"""
        mock_checker = Mock()
        mock_checker.check_and_notify.side_effect = Exception("Test error")
        mock_checker_class.return_value = mock_checker
        
        from temp_checker_refactored import main
        
        with pytest.raises(Exception):
            main()
        
        mock_logger.error.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])