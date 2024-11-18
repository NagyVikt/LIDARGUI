# config/config.py

import json
import os

# Default settings
DEFAULT_SETTINGS = {
    "LED_CONTROL": 69,
    "MAX_LEDS_ROW": 15,
    "WINDOWS": True
}

# Path to settings file
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
    else:
        settings = DEFAULT_SETTINGS
        # Save default settings to file
        save_settings(settings)
    return settings

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

# Load settings at module import
settings = load_settings()
LED_CONTROL = settings.get("LED_CONTROL", DEFAULT_SETTINGS["LED_CONTROL"])
MAX_LEDS_ROW = settings.get("MAX_LEDS_ROW", DEFAULT_SETTINGS["MAX_LEDS_ROW"])
WINDOWS = settings.get("WINDOWS", DEFAULT_SETTINGS["WINDOWS"])
