import json
import os
import platform

# Detect operating system
IS_WINDOWS = platform.system() == "Windows"

# Path to settings file
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                print("Error decoding settings.json. Using default settings.")
                settings = create_default_settings()
                save_settings(settings)
    else:
        settings = create_default_settings()
        save_settings(settings)
    # Override WINDOWS setting based on detected OS
    settings["WINDOWS"] = IS_WINDOWS
    return settings

def save_settings(settings):
    # Do not save the WINDOWS setting to settings.json
    settings_to_save = settings.copy()
    settings_to_save.pop("WINDOWS", None)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings_to_save, f, indent=4)

def create_default_settings():
    # Default settings (excluding WINDOWS)
    settings = {
        "LED_CONTROL": 69,
        "MAX_LEDS_ROW": 15
    }
    return settings

# Load settings
settings = load_settings()
LED_CONTROL = settings["LED_CONTROL"]
MAX_LEDS_ROW = settings["MAX_LEDS_ROW"]
WINDOWS = settings["WINDOWS"]
