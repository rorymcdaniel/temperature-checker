#!/usr/bin/env python3
"""
Temperature Checker - Monitor outdoor temperature and send Telegram notifications
for opening/closing windows based on configurable thresholds and modes.
"""

import os
import sqlite3
import json
import requests
import logging
from datetime import datetime, time
from typing import Optional, Tuple, Dict, Any, Protocol, Union
from dataclasses import dataclass
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('temp_checker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class AppState:
    window_state: str
    mode: str
    last_notification_type: Optional[str]
    last_notification_time: Optional[datetime]

@dataclass
class WeatherData:
    current_temp: float
    daily_high: float
    daily_low: float

@dataclass 
class Config:
    """Configuration class with proper types"""
    db_path: str
    zip_code: str
    telegram_token: str
    telegram_chat_id: str
    close_windows_temp: float
    open_windows_temp: float
    forecast_high_threshold: float
    heating_close_temp: float
    heating_open_temp: float
    heating_forecast_low_threshold: float
    quiet_start_hour: int
    quiet_start_minute: int
    quiet_end_hour: int
    quiet_end_minute: int
    default_mode: str

class DatabaseInterface(Protocol):
    """Protocol for database operations"""
    def init_database(self, schema_path: str) -> None: ...
    def get_app_state(self, default_mode: str = 'cooling') -> AppState: ...
    def update_app_state(self, window_state: Optional[str] = None, mode: Optional[str] = None, 
                        last_notification_type: Optional[str] = None) -> None: ...
    def record_temperature(self, weather_data: WeatherData, zip_code: str) -> None: ...
    def record_notification(self, notification_type: str, current_temp: float,
                          forecast_high: float, forecast_low: float, 
                          message: str, sent_successfully: bool, error_message: Optional[str] = None) -> None: ...

class WeatherInterface(Protocol):
    """Protocol for weather data fetching"""
    def get_coordinates_from_zip(self, zip_code: str) -> Tuple[float, float]: ...
    def fetch_weather_data(self, zip_code: str) -> Optional[WeatherData]: ...

class NotificationInterface(Protocol):
    """Protocol for notifications"""
    def send_message(self, message: str, token: str, chat_id: str) -> bool: ...

class TimeInterface(Protocol):
    """Protocol for time operations"""
    def now(self) -> datetime: ...

class DatabaseAdapter:
    """Database adapter for SQLite operations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def init_database(self, schema_path: str) -> None:
        """Initialize database with schema"""
        with sqlite3.connect(self.db_path) as conn:
            with open(schema_path, 'r') as f:
                conn.executescript(f.read())
            conn.commit()
    
    def get_app_state(self, default_mode: str = 'cooling') -> AppState:
        """Get current application state from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT window_state, mode, last_notification_type, last_notification_time
                FROM app_state WHERE id = 1
            """)
            row = cursor.fetchone()
            
            if row:
                last_notif_time = None
                if row[3]:
                    last_notif_time = datetime.fromisoformat(row[3])
                
                return AppState(
                    window_state=row[0],
                    mode=row[1],
                    last_notification_type=row[2],
                    last_notification_time=last_notif_time
                )
            else:
                return AppState(
                    window_state='closed',
                    mode=default_mode,
                    last_notification_type=None,
                    last_notification_time=None
                )
    
    def update_app_state(self, window_state: Optional[str] = None, mode: Optional[str] = None, 
                        last_notification_type: Optional[str] = None) -> None:
        """Update application state in database"""
        with sqlite3.connect(self.db_path) as conn:
            updates = []
            params = []
            
            if window_state:
                updates.append("window_state = ?")
                params.append(window_state)
            
            if mode:
                updates.append("mode = ?")
                params.append(mode)
            
            if last_notification_type:
                updates.append("last_notification_type = ?")
                params.append(last_notification_type)
                updates.append("last_notification_time = ?")
                params.append(datetime.now().isoformat())
            
            if updates:
                updates.append("updated_at = ?")
                params.append(datetime.now().isoformat())
                params.append("1")  # WHERE id = 1
                
                query = f"UPDATE app_state SET {', '.join(updates)} WHERE id = ?"
                conn.execute(query, params)
                conn.commit()
    
    def record_temperature(self, weather_data: WeatherData, zip_code: str) -> None:
        """Record temperature reading in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO temperature_readings 
                (current_temp, daily_high_forecast, daily_low_forecast, zip_code)
                VALUES (?, ?, ?, ?)
            """, (weather_data.current_temp, weather_data.daily_high, 
                  weather_data.daily_low, zip_code))
            conn.commit()
    
    def record_notification(self, notification_type: str, current_temp: float,
                          forecast_high: float, forecast_low: float, 
                          message: str, sent_successfully: bool, error_message: Optional[str] = None) -> None:
        """Record notification in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO notifications 
                (notification_type, current_temp, forecast_high, forecast_low, 
                 message, sent_successfully, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (notification_type, current_temp, forecast_high, forecast_low,
                  message, sent_successfully, error_message))
            conn.commit()

class WeatherAdapter:
    """Weather data adapter using Open-Meteo API"""
    
    def get_coordinates_from_zip(self, zip_code: str) -> Tuple[float, float]:
        """Get latitude and longitude from ZIP code using a geocoding service"""
        url = f"https://api.zippopotam.us/us/{zip_code}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                lat = float(data['places'][0]['latitude'])
                lon = float(data['places'][0]['longitude'])
                return lat, lon
            else:
                logger.error(f"Failed to get coordinates for ZIP {zip_code}")
                return 0.0, 0.0
        except Exception as e:
            logger.error(f"Error getting coordinates: {e}")
            return 0.0, 0.0
    
    def fetch_weather_data(self, zip_code: str) -> Optional[WeatherData]:
        """Fetch current weather and daily forecast from Open-Meteo API"""
        if not zip_code:
            logger.error("ZIP_CODE not provided")
            return None
        
        lat, lon = self.get_coordinates_from_zip(zip_code)
        if lat == 0.0 and lon == 0.0:
            return None
        
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': str(lat),
            'longitude': str(lon),
            'current': 'temperature_2m',
            'daily': 'temperature_2m_max,temperature_2m_min',
            'temperature_unit': 'fahrenheit',
            'timezone': 'auto'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                current_temp = data['current']['temperature_2m']
                daily_high = data['daily']['temperature_2m_max'][0]
                daily_low = data['daily']['temperature_2m_min'][0]
                
                return WeatherData(
                    current_temp=current_temp,
                    daily_high=daily_high,
                    daily_low=daily_low
                )
            else:
                logger.error(f"Weather API returned status {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")
            return None

class TelegramAdapter:
    """Telegram notification adapter"""
    
    def send_message(self, message: str, token: str, chat_id: str) -> bool:
        """Send message via Telegram bot"""
        if not token or not chat_id:
            logger.error("Telegram credentials not provided")
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"Telegram message sent: {message}")
                return True
            else:
                logger.error(f"Telegram API returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

class TimeAdapter:
    """Time operations adapter"""
    
    def now(self) -> datetime:
        return datetime.now()

class TemperatureChecker:
    def __init__(self, 
                 database: Optional[DatabaseInterface] = None,
                 weather: Optional[WeatherInterface] = None,
                 notification: Optional[NotificationInterface] = None,
                 time_provider: Optional[TimeInterface] = None,
                 config: Optional[Config] = None):
        
        # Load environment variables if no config provided
        if config is None:
            load_dotenv()
            config = self._load_config_from_env()
        
        self.config = config
        
        # Use dependency injection or create default adapters
        self.database = database or DatabaseAdapter(config.db_path)
        self.weather = weather or WeatherAdapter()
        self.notification = notification or TelegramAdapter()
        self.time_provider = time_provider or TimeAdapter()
        
        # Initialize database
        try:
            self.database.init_database('database_schema.sql')
        except FileNotFoundError:
            # For tests, we might not have the schema file
            pass
    
    def _load_config_from_env(self) -> Config:
        """Load configuration from environment variables"""
        return Config(
            db_path=os.getenv('DATABASE_PATH', 'temperature_checker.db'),
            zip_code=os.getenv('ZIP_CODE', ''),
            telegram_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID', ''),
            close_windows_temp=float(os.getenv('CLOSE_WINDOWS_TEMP', '78')),
            open_windows_temp=float(os.getenv('OPEN_WINDOWS_TEMP', '76')),
            forecast_high_threshold=float(os.getenv('FORECAST_HIGH_THRESHOLD', '80')),
            heating_close_temp=float(os.getenv('HEATING_CLOSE_TEMP', '55')),
            heating_open_temp=float(os.getenv('HEATING_OPEN_TEMP', '65')),
            heating_forecast_low_threshold=float(os.getenv('HEATING_FORECAST_LOW_THRESHOLD', '70')),
            quiet_start_hour=int(os.getenv('QUIET_START_HOUR', '22')),
            quiet_start_minute=int(os.getenv('QUIET_START_MINUTE', '30')),
            quiet_end_hour=int(os.getenv('QUIET_END_HOUR', '7')),
            quiet_end_minute=int(os.getenv('QUIET_END_MINUTE', '0')),
            default_mode=os.getenv('DEFAULT_MODE', 'cooling')
        )
    
    def is_quiet_hours(self, current_time: Optional[datetime] = None) -> bool:
        """Check if current time is within quiet hours"""
        if current_time is None:
            current_time = self.time_provider.now()
        
        time_only = current_time.time()
        
        quiet_start = time(self.config.quiet_start_hour, self.config.quiet_start_minute)
        quiet_end = time(self.config.quiet_end_hour, self.config.quiet_end_minute)
        
        # Handle overnight quiet hours (e.g., 22:30 - 07:00)
        if quiet_start > quiet_end:
            return time_only >= quiet_start or time_only <= quiet_end
        else:
            return quiet_start <= time_only <= quiet_end
    
    def should_send_notification(self, notification_type: str, app_state: AppState, 
                               current_time: Optional[datetime] = None) -> bool:
        """Determine if we should send a notification based on current state"""
        if current_time is None:
            current_time = self.time_provider.now()
            
        # Check quiet hours
        if self.is_quiet_hours(current_time):
            logger.info("Currently in quiet hours, skipping notification")
            return False
        
        # Check if we already sent this type of notification recently
        if (app_state.last_notification_type == notification_type and 
            app_state.last_notification_time):
            # Don't send same notification type within 30 minutes
            time_diff = current_time - app_state.last_notification_time
            if time_diff.total_seconds() < 1800:  # 30 minutes
                logger.info(f"Already sent {notification_type} notification recently")
                return False
        
        return True
    
    def create_notification_message(self, notification_type: str, weather_data: WeatherData, 
                                   mode: str) -> str:
        """Create notification message based on type and mode"""
        if notification_type == 'close_windows':
            if mode == 'cooling':
                emoji = "🌡️"
                reason = "Time to close the windows and turn on the AC!"
            else:  # heating
                emoji = "🥶"
                reason = "Getting too cold! Time to close the windows and turn on heat."
        else:  # open_windows
            if mode == 'cooling':
                emoji = "🌬️"
                reason = "Perfect time to open the windows and enjoy the fresh air!"
            else:  # heating
                emoji = "☀️"
                reason = "Nice and warm! Perfect time to open the windows."
        
        return (f"{emoji} <b>{'Close' if notification_type == 'close_windows' else 'Open'} Windows</b>\n\n"
                f"Current temperature: {weather_data.current_temp}°F\n"
                f"Daily high forecast: {weather_data.daily_high}°F\n\n"
                f"{reason}")
    
    def check_cooling_mode_conditions(self, weather_data: WeatherData, app_state: AppState) -> Optional[str]:
        """Check cooling mode conditions and return notification type if needed"""
        # Close windows notification
        if (app_state.window_state == 'open' and 
            weather_data.current_temp >= self.config.close_windows_temp and
            weather_data.daily_high > self.config.forecast_high_threshold):
            return 'close_windows'
        
        # Open windows notification
        elif (app_state.window_state == 'closed' and 
              weather_data.current_temp <= self.config.open_windows_temp):
            return 'open_windows'
        
        return None
    
    def check_heating_mode_conditions(self, weather_data: WeatherData, app_state: AppState) -> Optional[str]:
        """Check heating mode conditions and return notification type if needed"""
        # Close windows notification (too cold)
        if (app_state.window_state == 'open' and 
            weather_data.current_temp <= self.config.heating_close_temp):
            return 'close_windows'
        
        # Open windows notification (warm enough)
        elif (app_state.window_state == 'closed' and 
              weather_data.current_temp >= self.config.heating_open_temp and
              weather_data.daily_high < self.config.heating_forecast_low_threshold):
            return 'open_windows'
        
        return None
    
    def process_notification(self, notification_type: str, weather_data: WeatherData, 
                           app_state: AppState) -> bool:
        """Process and send a notification"""
        message = self.create_notification_message(notification_type, weather_data, app_state.mode)
        
        success = self.notification.send_message(
            message, 
            self.config.telegram_token, 
            self.config.telegram_chat_id
        )
        
        self.database.record_notification(
            notification_type, weather_data.current_temp,
            weather_data.daily_high, weather_data.daily_low,
            message, success
        )
        
        if success:
            new_window_state = 'closed' if notification_type == 'close_windows' else 'open'
            self.database.update_app_state(
                window_state=new_window_state, 
                last_notification_type=notification_type
            )
        
        return success
    
    def check_and_notify(self) -> None:
        """Main logic to check temperature and send notifications"""
        logger.info("Starting temperature check...")
        
        # Fetch weather data
        weather_data = self.weather.fetch_weather_data(self.config.zip_code)
        if not weather_data:
            logger.error("Failed to fetch weather data")
            return
        
        # Record temperature
        self.database.record_temperature(weather_data, self.config.zip_code)
        
        # Get current app state
        app_state = self.database.get_app_state(self.config.default_mode)
        
        logger.info(f"Current temp: {weather_data.current_temp}°F, "
                   f"High: {weather_data.daily_high}°F, "
                   f"Low: {weather_data.daily_low}°F, "
                   f"Mode: {app_state.mode}, "
                   f"Windows: {app_state.window_state}")
        
        # Determine if notification needed based on mode
        notification_type = None
        if app_state.mode == 'cooling':
            notification_type = self.check_cooling_mode_conditions(weather_data, app_state)
        elif app_state.mode == 'heating':
            notification_type = self.check_heating_mode_conditions(weather_data, app_state)
        
        # Send notification if needed
        if notification_type and self.should_send_notification(notification_type, app_state):
            self.process_notification(notification_type, weather_data, app_state)

def main() -> None:
    try:
        checker = TemperatureChecker()
        checker.check_and_notify()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()