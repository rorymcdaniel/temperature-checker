# Temperature Checker

A Python application that monitors outdoor temperature and sends Telegram notifications for opening/closing windows based on configurable thresholds and seasonal modes.

## Features

- **Dual Mode Operation**: Cooling mode (summer) and heating mode (winter)
- **Smart Notifications**: Only sends relevant notifications based on current conditions and forecast
- **Quiet Hours**: No notifications during sleep hours (configurable)
- **State Tracking**: Remembers window state and prevents duplicate notifications
- **Manual Override**: Utility script to manually adjust window state
- **Weather Integration**: Uses Open-Meteo free weather API (no API key required)
- **Telegram Integration**: Sends formatted notifications via Telegram bot

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Location Settings
ZIP_CODE=12345

# Telegram Bot Configuration  
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Temperature Thresholds (Fahrenheit)
CLOSE_WINDOWS_TEMP=78
OPEN_WINDOWS_TEMP=76
FORECAST_HIGH_THRESHOLD=80

# Heating mode thresholds
HEATING_CLOSE_TEMP=55
HEATING_OPEN_TEMP=65
HEATING_FORECAST_LOW_THRESHOLD=70

# Quiet Hours (24-hour format)
QUIET_START_HOUR=22
QUIET_START_MINUTE=30
QUIET_END_HOUR=7
QUIET_END_MINUTE=0

# Default mode: 'cooling' or 'heating'
DEFAULT_MODE=cooling
```

### 3. Telegram Bot Setup

1. Create a new bot by messaging [@BotFather](https://t.me/botfather) on Telegram
2. Use `/newbot` command and follow instructions
3. Copy the bot token to your `.env` file
4. Start a chat with your bot and send any message
5. Get your chat ID by visiting: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
6. Copy the chat ID to your `.env` file

### 4. Initialize Database

The database will be automatically initialized on first run:

```bash
python temp_checker.py
```

## Usage

### Manual Execution

Run the temperature checker once:

```bash
python temp_checker.py
```

### Automated Execution (Recommended)

Set up a crontab to run every 10 minutes:

```bash
crontab -e
```

Add this line (adjust path as needed):

```bash
*/10 * * * * cd /path/to/temperature-checker && /usr/bin/python3 temp_checker.py
```

### Manual State Management

Use the utility script to manually adjust settings:

```bash
# Show current status
python set_window_state.py status

# Set window state
python set_window_state.py open
python set_window_state.py closed

# Change mode
python set_window_state.py mode cooling
python set_window_state.py mode heating

# Reset notification state (allows immediate notifications)
python set_window_state.py reset
```

## How It Works

### Cooling Mode (Summer)
- **Close Windows**: When temperature ≥ 78°F AND daily high forecast > 80°F
- **Open Windows**: When temperature ≤ 76°F

### Heating Mode (Winter)  
- **Close Windows**: When temperature ≤ 55°F
- **Open Windows**: When temperature ≥ 65°F AND daily high forecast < 70°F

### Smart Features
- **Quiet Hours**: No notifications between 10:30 PM - 7:00 AM
- **Duplicate Prevention**: Won't send same notification type within 30 minutes
- **State Awareness**: Tracks whether windows are open/closed
- **Forecast Integration**: Uses daily forecast to make smarter decisions

## Database Schema

The application uses SQLite with three main tables:

- `app_state`: Current window state, mode, and last notification info
- `temperature_readings`: Historical temperature and forecast data
- `notifications`: Log of all notifications sent

## Files

- `temp_checker.py`: Main application
- `set_window_state.py`: Utility for manual state management
- `database_schema.sql`: Database initialization script
- `.env.example`: Configuration template
- `requirements.txt`: Python dependencies

## Troubleshooting

### Check Logs
Logs are written to `temp_checker.log` and console:

```bash
tail -f temp_checker.log
```

### Verify Configuration
```bash
python set_window_state.py status
```

### Test Telegram Bot
Make sure your bot token and chat ID are correct by testing a manual message.

### Weather API Issues
The app uses Open-Meteo which requires no API key. If weather data fails, check your internet connection and ZIP code format.

## Customization

All thresholds and settings are configurable via the `.env` file. You can adjust:

- Temperature thresholds for both modes
- Quiet hours window
- Default operating mode
- Database file location

The 10-minute cron interval is recommended but can be adjusted based on your needs.