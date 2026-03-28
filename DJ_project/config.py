import os
from dotenv import load_dotenv

load_dotenv()

JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "")
JAMENDO_BASE_URL = "https://api.jamendo.com/v3.0"

CACHE_DIR = "track_cache"
HISTORY_FILE = "track_history.json"

SERIAL_PORT = "/dev/tty.usbmodem14201" 
SERIAL_BAUDRATE = 115200
SERIAL_INTERVAL = 0.05

# --- Duration limits (seconds) ---
MIN_TRACK_DURATION = 120
MAX_TRACK_DURATION = 600

# --- LED lighting per mood ---
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

RED_CHANNEL_SCALE = 0.63

# --- Mood-level fallback settings ---
MOOD_TAGS = {
    "CALM": ["chillout", "lounge"],
    "WARM": ["house", "funk"],
    "ENERGETIC": ["dance", "electronic"],
    "HYPE": ["edm", "party", "dance"],
}

MOOD_BPM = {
    "CALM": (68, 92),
    "WARM": (90, 116),
    "ENERGETIC": (112, 132),
    "HYPE": (126, 150),
}

MOOD_MIN_RMS = {
    "CALM": 0.02,
    "WARM": 0.04,
    "ENERGETIC": 0.06,
    "HYPE": 0.08,
}

# --- Exact room-energy profile (1..10) ---
ENERGY_PROFILE = {
    1: {
        "mood": "CALM",
        "tags": ["chillout", "lounge"],
        "speed": "verylow",
        "bpm_range": (68, 80),
        "min_rms": 0.02,
    },
    2: {
        "mood": "CALM",
        "tags": ["chillout", "lounge"],
        "speed": "low",
        "bpm_range": (74, 86),
        "min_rms": 0.025,
    },
    3: {
        "mood": "CALM",
        "tags": ["chillout", "lounge"],
        "speed": "low",
        "bpm_range": (80, 92),
        "min_rms": 0.03,
    },
    4: {
        "mood": "WARM",
        "tags": ["house", "funk"],
        "speed": "medium",
        "bpm_range": (88, 100),
        "min_rms": 0.04,
    },
    5: {
        "mood": "WARM",
        "tags": ["house", "funk"],
        "speed": "medium",
        "bpm_range": (96, 108),
        "min_rms": 0.05,
    },
    6: {
        "mood": "WARM",
        "tags": ["house", "dance", "funk"],
        "speed": "high",
        "bpm_range": (104, 116),
        "min_rms": 0.06,
    },
    7: {
        "mood": "ENERGETIC",
        "tags": ["dance", "electronic"],
        "speed": "high",
        "bpm_range": (112, 124),
        "min_rms": 0.07,
    },
    8: {
        "mood": "ENERGETIC",
        "tags": ["dance", "electronic", "house"],
        "speed": "high",
        "bpm_range": (120, 132),
        "min_rms": 0.08,
    },
    9: {
        "mood": "HYPE",
        "tags": ["edm", "party", "dance"],
        "speed": "veryhigh",
        "bpm_range": (126, 140),
        "min_rms": 0.09,
    },
    10: {
        "mood": "HYPE",
        "tags": ["edm", "party", "dance"],
        "speed": "veryhigh",
        "bpm_range": (134, 150),
        "min_rms": 0.10,
    },
}


def clamp_energy(level):
    try:
        level = int(level)
    except (TypeError, ValueError):
        level = 5
    return max(1, min(10, level))


def get_energy_profile(level):
    return ENERGY_PROFILE[clamp_energy(level)]