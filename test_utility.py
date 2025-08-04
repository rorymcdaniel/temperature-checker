#!/usr/bin/env python3
"""
Tests for the utility script functionality
"""

import pytest
import os
import sys
import tempfile
import sqlite3
from unittest.mock import patch
from io import StringIO

# Import the utility functions by reading and executing the script
import importlib.util


class TestUtilityScript:
    """Test cases for the utility script functions"""
    
    def setup_method(self):
        """Setup test environment with temporary database"""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # Initialize test database schema
        self._init_test_schema()
        
        # Load the utility script module
        spec = importlib.util.spec_from_file_location(
            "set_window_state", 
            "/Users/rory/PycharmProjects/temperature-checker/set_window_state.py"
        )
        self.utility_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.utility_module)
    
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
        
        with sqlite3.connect(self.temp_db_path) as conn:
            conn.executescript(schema)
            conn.commit()
    
    def _add_test_data(self):
        """Add some test data to the database"""
        with sqlite3.connect(self.temp_db_path) as conn:
            # Add temperature readings
            conn.execute("""
                INSERT INTO temperature_readings (current_temp, daily_high_forecast, daily_low_forecast, zip_code)
                VALUES (75.0, 85.0, 65.0, '10001')
            """)
            
            # Add notifications
            conn.execute("""
                INSERT INTO notifications (notification_type, current_temp, forecast_high, forecast_low, message, sent_successfully)
                VALUES ('close_windows', 78.0, 85.0, 65.0, 'Test message', 1)
            """)
            
            conn.commit()
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    def test_show_status_basic(self):
        """Test show_status function with basic data"""
        # Set DATABASE_PATH environment variable
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            with sqlite3.connect(self.temp_db_path) as conn:
                # Capture stdout
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    self.utility_module.show_status(conn)
                
                output = captured_output.getvalue()
                assert 'Window State: closed' in output
                assert 'Mode: cooling' in output
                assert 'Last Notification: None' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    def test_show_status_with_data(self):
        """Test show_status function with additional data"""
        self._add_test_data()
        
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            with sqlite3.connect(self.temp_db_path) as conn:
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    self.utility_module.show_status(conn)
                
                output = captured_output.getvalue()
                assert 'Window State: closed' in output
                assert 'Recent Temperature Readings:' in output
                assert '75.0°F' in output
                assert 'Recent Notifications:' in output
                assert 'close_windows' in output
    
    def test_set_window_state_open(self):
        """Test setting window state to open"""
        with sqlite3.connect(self.temp_db_path) as conn:
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.set_window_state(conn, 'open')
            
            # Verify database was updated
            cursor = conn.execute("SELECT window_state FROM app_state WHERE id = 1")
            result = cursor.fetchone()
            assert result[0] == 'open'
            
            # Verify output message
            output = captured_output.getvalue()
            assert 'Window state set to: open' in output
    
    def test_set_window_state_closed(self):
        """Test setting window state to closed"""
        with sqlite3.connect(self.temp_db_path) as conn:
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.set_window_state(conn, 'closed')
            
            # Verify database was updated
            cursor = conn.execute("SELECT window_state FROM app_state WHERE id = 1")
            result = cursor.fetchone()
            assert result[0] == 'closed'
            
            # Verify output message
            output = captured_output.getvalue()
            assert 'Window state set to: closed' in output
    
    def test_set_mode_heating(self):
        """Test setting mode to heating"""
        with sqlite3.connect(self.temp_db_path) as conn:
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.set_mode(conn, 'heating')
            
            # Verify database was updated
            cursor = conn.execute("SELECT mode FROM app_state WHERE id = 1")
            result = cursor.fetchone()
            assert result[0] == 'heating'
            
            # Verify output message
            output = captured_output.getvalue()
            assert 'Mode set to: heating' in output
    
    def test_set_mode_cooling(self):
        """Test setting mode to cooling"""
        with sqlite3.connect(self.temp_db_path) as conn:
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.set_mode(conn, 'cooling')
            
            # Verify database was updated
            cursor = conn.execute("SELECT mode FROM app_state WHERE id = 1")
            result = cursor.fetchone()
            assert result[0] == 'cooling'
            
            # Verify output message
            output = captured_output.getvalue()
            assert 'Mode set to: cooling' in output
    
    def test_reset_notification_state(self):
        """Test resetting notification state"""
        # First set some notification state
        with sqlite3.connect(self.temp_db_path) as conn:
            conn.execute("""
                UPDATE app_state 
                SET last_notification_type = 'close_windows', 
                    last_notification_time = '2023-01-01T10:00:00'
                WHERE id = 1
            """)
            conn.commit()
            
            # Verify it was set
            cursor = conn.execute("SELECT last_notification_type FROM app_state WHERE id = 1")
            result = cursor.fetchone()
            assert result[0] == 'close_windows'
            
            # Reset notification state
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.reset_notification_state(conn)
            
            # Verify it was reset
            cursor = conn.execute("SELECT last_notification_type, last_notification_time FROM app_state WHERE id = 1")
            result = cursor.fetchone()
            assert result[0] is None
            assert result[1] is None
            
            # Verify output message
            output = captured_output.getvalue()
            assert 'Notification state reset' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'status'])
    def test_main_status_command(self):
        """Test main function with status command"""
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.main()
            
            output = captured_output.getvalue()
            assert 'Window State:' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'open'])
    def test_main_open_command(self):
        """Test main function with open command"""
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.main()
            
            output = captured_output.getvalue()
            assert 'Window state set to: open' in output
            
            # Verify database was updated
            with sqlite3.connect(self.temp_db_path) as conn:
                cursor = conn.execute("SELECT window_state FROM app_state WHERE id = 1")
                result = cursor.fetchone()
                assert result[0] == 'open'
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'closed'])
    def test_main_closed_command(self):
        """Test main function with closed command"""
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.main()
            
            output = captured_output.getvalue()
            assert 'Window state set to: closed' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'mode', 'heating'])
    def test_main_mode_heating_command(self):
        """Test main function with mode heating command"""
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.main()
            
            output = captured_output.getvalue()
            assert 'Mode set to: heating' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'mode', 'cooling'])
    def test_main_mode_cooling_command(self):
        """Test main function with mode cooling command"""
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.main()
            
            output = captured_output.getvalue()
            assert 'Mode set to: cooling' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'reset'])
    def test_main_reset_command(self):
        """Test main function with reset command"""
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                self.utility_module.main()
            
            output = captured_output.getvalue()
            assert 'Notification state reset' in output
    
    @patch('sys.argv', ['set_window_state.py'])
    def test_main_no_arguments(self):
        """Test main function with no arguments (should show usage)"""
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            with pytest.raises(SystemExit):
                self.utility_module.main()
        
        output = captured_output.getvalue()
        assert 'Usage:' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'invalid'])
    def test_main_invalid_command(self):
        """Test main function with invalid command"""
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                with pytest.raises(SystemExit):
                    self.utility_module.main()
            
            output = captured_output.getvalue()
            assert 'Invalid command' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'mode', 'invalid'])
    def test_main_invalid_mode(self):
        """Test main function with invalid mode"""
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                with pytest.raises(SystemExit):
                    self.utility_module.main()
            
            output = captured_output.getvalue()
            assert 'Mode must be' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'mode'])
    def test_main_mode_no_argument(self):
        """Test main function with mode but no argument"""
        with patch.dict('os.environ', {'DATABASE_PATH': self.temp_db_path}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                with pytest.raises(SystemExit):
                    self.utility_module.main()
            
            output = captured_output.getvalue()
            assert 'Invalid command' in output
    
    @patch.dict('os.environ', {'DATABASE_PATH': ''})
    @patch('sys.argv', ['set_window_state.py', 'status'])
    def test_main_database_error(self):
        """Test main function with database error"""
        # Use non-existent database path
        with patch.dict('os.environ', {'DATABASE_PATH': '/nonexistent/path.db'}):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                with pytest.raises(SystemExit):
                    self.utility_module.main()
            
            output = captured_output.getvalue()
            # The actual error is printed to stdout, not stderr
            assert 'Database error:' in output or 'unable to open database file' in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])