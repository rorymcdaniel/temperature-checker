#!/usr/bin/env python3
"""
Utility script to manually set window state and mode for the temperature checker.
"""

import sys
import sqlite3
import os
from datetime import datetime
from typing import List
from dotenv import load_dotenv

def main() -> None:
    load_dotenv()
    db_path = os.getenv('DATABASE_PATH', 'temperature_checker.db')
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python set_window_state.py status                    # Show current status")
        print("  python set_window_state.py open                     # Set windows to open")
        print("  python set_window_state.py closed                   # Set windows to closed") 
        print("  python set_window_state.py mode cooling             # Set mode to cooling")
        print("  python set_window_state.py mode heating             # Set mode to heating")
        print("  python set_window_state.py reset                    # Reset notification state")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    try:
        with sqlite3.connect(db_path) as conn:
            if command == 'status':
                show_status(conn)
            elif command in ['open', 'closed']:
                set_window_state(conn, command)
            elif command == 'mode' and len(sys.argv) > 2:
                mode = sys.argv[2].lower()
                if mode in ['cooling', 'heating']:
                    set_mode(conn, mode)
                else:
                    print("Mode must be 'cooling' or 'heating'")
                    sys.exit(1)
            elif command == 'reset':
                reset_notification_state(conn)
            else:
                print("Invalid command. Use 'status', 'open', 'closed', 'mode', or 'reset'")
                sys.exit(1)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def show_status(conn: sqlite3.Connection) -> None:
    """Show current application status"""
    cursor = conn.execute("""
        SELECT window_state, mode, last_notification_type, last_notification_time, updated_at
        FROM app_state WHERE id = 1
    """)
    row = cursor.fetchone()
    
    if row:
        print(f"Window State: {row[0]}")
        print(f"Mode: {row[1]}")
        print(f"Last Notification: {row[2] or 'None'}")
        print(f"Last Notification Time: {row[3] or 'None'}")
        print(f"Last Updated: {row[4] or 'None'}")
    else:
        print("No state found in database")
    
    # Show recent temperature readings
    cursor = conn.execute("""
        SELECT timestamp, current_temp, daily_high_forecast, daily_low_forecast
        FROM temperature_readings 
        ORDER BY timestamp DESC 
        LIMIT 3
    """)
    readings = cursor.fetchall()
    
    if readings:
        print("\nRecent Temperature Readings:")
        for reading in readings:
            print(f"  {reading[0]}: {reading[1]}°F (High: {reading[2]}°F, Low: {reading[3]}°F)")
    
    # Show recent notifications
    cursor = conn.execute("""
        SELECT timestamp, notification_type, current_temp, sent_successfully
        FROM notifications 
        ORDER BY timestamp DESC 
        LIMIT 3
    """)
    notifications = cursor.fetchall()
    
    if notifications:
        print("\nRecent Notifications:")
        for notif in notifications:
            status = "✓" if notif[3] else "✗"
            print(f"  {notif[0]}: {notif[1]} at {notif[2]}°F {status}")

def set_window_state(conn: sqlite3.Connection, state: str) -> None:
    """Set window state"""
    conn.execute("""
        UPDATE app_state 
        SET window_state = ?, updated_at = ?
        WHERE id = 1
    """, (state, datetime.now().isoformat()))
    conn.commit()
    print(f"Window state set to: {state}")

def set_mode(conn: sqlite3.Connection, mode: str) -> None:
    """Set operating mode"""
    conn.execute("""
        UPDATE app_state 
        SET mode = ?, updated_at = ?
        WHERE id = 1
    """, (mode, datetime.now().isoformat()))
    conn.commit()
    print(f"Mode set to: {mode}")

def reset_notification_state(conn: sqlite3.Connection) -> None:
    """Reset notification state to allow immediate notifications"""
    conn.execute("""
        UPDATE app_state 
        SET last_notification_type = NULL, last_notification_time = NULL, updated_at = ?
        WHERE id = 1
    """, (datetime.now().isoformat(),))
    conn.commit()
    print("Notification state reset - notifications can be sent immediately")

if __name__ == "__main__":
    main()