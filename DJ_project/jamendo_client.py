# jamendo_client.py

import os
import requests
from config import (
    JAMENDO_CLIENT_ID,
    JAMENDO_BASE_URL,
    CACHE_DIR,
    MIN_TRACK_DURATION,
    MAX_TRACK_DURATION,
)


class JamendoClient:
    def __init__(self):
        if not JAMENDO_CLIENT_ID:
            raise ValueError("Missing JAMENDO_CLIENT_ID in .env")

    def search_tracks(self, tags, limit=20):
        url = f"{JAMENDO_BASE_URL}/tracks/"
        params = {
            "client_id":   JAMENDO_CLIENT_ID,
            "format":      "json",
            # Fetch more than needed so local filters still leave enough tracks
            "limit":       50,
            "include":     "musicinfo",
            "audioformat": "mp31",
            "tags":        ",".join(tags),
            # Order by popularity so real DJ tracks bubble up first,
            # not obscure ambient pieces that happen to have the right tag.
            "order":       "popularity_total",
        }

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json().get("results", [])

        tracks = []
        for item in data:
            musicinfo = item.get("musicinfo", {})
            duration  = item.get("duration", 0)

            # --- Local duration filter ---
            # Keeps tracks between 2 and 10 minutes.
            # Short clips are loops/jingles; very long ones are ambient pads.
            if not (MIN_TRACK_DURATION <= duration <= MAX_TRACK_DURATION):
                continue

            tracks.append({
                "id":        str(item.get("id")),
                "name":      item.get("name"),
                "artist":    item.get("artist_name"),
                "audio_url": item.get("audio"),
                "duration":  duration,
                "tags":      musicinfo.get("tags", {}),
                # Jamendo only fills bpm/key for beat-driven tracks.
                # Ambient/melody tracks almost always return None here —
                # the agent will hard-reject those before scoring.
                "bpm":       musicinfo.get("bpm"),
                "key":       musicinfo.get("key"),
            })

        # Return up to the originally requested limit after local filtering
        return tracks[:limit]

    def download_track(self, track):
        os.makedirs(CACHE_DIR, exist_ok=True)

        track_id = track["id"]
        filename = f"{track_id}.mp3"
        filepath = os.path.join(CACHE_DIR, filename)

        if os.path.exists(filepath):
            return filepath

        audio_url = track.get("audio_url")
        if not audio_url:
            return None

        try:
            response = requests.get(audio_url, stream=True, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"  [download error] {track.get('name', track_id)}: {e}")
            return None

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return filepath