# jamendo_client.py

import os
import requests
from config import JAMENDO_CLIENT_ID, JAMENDO_BASE_URL, CACHE_DIR


class JamendoClient:
    def __init__(self):
        if not JAMENDO_CLIENT_ID:
            raise ValueError("Missing JAMENDO_CLIENT_ID in .env")

    def search_tracks(self, tags, limit=20):
        url = f"{JAMENDO_BASE_URL}/tracks/"
        params = {
            "client_id": JAMENDO_CLIENT_ID,
            "format": "json",
            "limit": limit,
            "include": "musicinfo",
            "audioformat": "mp31",
            "tags": ",".join(tags),
        }

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json().get("results", [])

        tracks = []
        for item in data:
            musicinfo = item.get("musicinfo", {})
            tracks.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "artist": item.get("artist_name"),
                "audio_url": item.get("audio"),
                "duration": item.get("duration", 0),
                "tags": musicinfo.get("tags", {}),
                "bpm": musicinfo.get("bpm"),
                "key": musicinfo.get("key"),
            })
        return tracks

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

        response = requests.get(audio_url, stream=True, timeout=30)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return filepath