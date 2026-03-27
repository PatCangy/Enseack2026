# config.py

import os
from dotenv import load_dotenv

load_dotenv()

JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "")
JAMENDO_BASE_URL = "https://api.jamendo.com/v3.0"

CACHE_DIR = "track_cache"
HISTORY_FILE = "history.json"

SERIAL_PORT = "COM3"          # change later
SERIAL_BAUDRATE = 115200
SERIAL_INTERVAL = 0.05        # 50 ms

MOOD_RGB = {
    "CALM": (0, 0, 255),
    "WARM": (255, 120, 0),
    "ENERGETIC": (255, 0, 120),
    "HYPE": (255, 0, 0),
}

MOOD_SIDE = {
    "CALM": 0b0001,
    "WARM": 0b0011,
    "ENERGETIC": 0b0111,
    "HYPE": 0b1111,
}

MOOD_TAGS = {
    "CALM": ["chillout", "ambient"],
    "WARM": ["house", "groove"],
    "ENERGETIC": ["dance", "electronic"],
    "HYPE": ["edm", "party"],
}

MOOD_BPM = {
    "CALM": (60, 95),
    "WARM": (90, 115),
    "ENERGETIC": (110, 130),
    "HYPE": (125, 150),
}

RED_CHANNEL_SCALE = 0.63