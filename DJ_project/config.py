# config.py

import os
from dotenv import load_dotenv

load_dotenv()

JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "")
JAMENDO_BASE_URL  = "https://api.jamendo.com/v3.0"

CACHE_DIR    = "track_cache"
HISTORY_FILE = "track_history.json"

SERIAL_PORT      = "COM3"    # change to your actual port
SERIAL_BAUDRATE  = 115200
SERIAL_INTERVAL  = 0.05      # 50 ms

# --- Duration limits (seconds) ---
# Applied locally after fetch — Jamendo API duration params are unreliable.
MIN_TRACK_DURATION = 120     # 2 min — rejects short loops and jingles
MAX_TRACK_DURATION = 600     # 10 min — rejects endless ambient pieces

# --- LED lighting per mood ---
MOOD_RGB = {
    "CALM":      (0,   0,   255),
    "WARM":      (255, 120, 0),
    "ENERGETIC": (255, 0,   120),
    "HYPE":      (255, 0,   0),
}

MOOD_SIDE = {
    "CALM":      0b0001,
    "WARM":      0b0011,
    "ENERGETIC": 0b0111,
    "HYPE":      0b1111,
}

# --- Tags sent to Jamendo search ---
# Kept broad enough to return results, but beat-oriented:
#   CALM:      chillout works well; replaced ambient (returns too many pure melody tracks)
#              with lounge which still has a beat
#   WARM:      house is reliable on Jamendo; added funk as backup
#   ENERGETIC: dance is the most reliable beat tag on Jamendo; kept electronic
#   HYPE:      edm is reliable; kept party as backup
# The BPM-null gate in dj_agent.py will reject any melodic tracks that slip through.
MOOD_TAGS = {
    "CALM":      ["chillout", "lounge"],
    "WARM":      ["house", "funk"],
    "ENERGETIC": ["dance", "electronic"],
    "HYPE":      ["edm", "party"],
}

# --- BPM range per mood ---
MOOD_BPM = {
    "CALM":      (60,  95),
    "WARM":      (90,  115),
    "ENERGETIC": (110, 130),
    "HYPE":      (125, 150),
}

# --- Minimum RMS energy floor per mood ---
# Used in dj_agent hard gate. Tracks below these are rejected before scoring.
# Pure melodies and ambient pads have very low RMS — this filters them out.
MOOD_MIN_RMS = {
    "CALM":      0.02,
    "WARM":      0.04,
    "ENERGETIC": 0.06,
    "HYPE":      0.08,
}

RED_CHANNEL_SCALE = 0.63