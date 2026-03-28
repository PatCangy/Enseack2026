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

    def search_tracks(self, tags, speed=None, limit=20, instrumental_only=True):
        url = f"{JAMENDO_BASE_URL}/tracks/"

        params = {
            "client_id": JAMENDO_CLIENT_ID,
            "format": "json",
            "limit": max(50, limit * 3),
            "include": "musicinfo",
            "audioformat": "mp31",
            "fuzzytags": ",".join(tags),
            "order": "popularity_total",
        }

        if speed:
            params["speed"] = speed

        if instrumental_only:
            params["vocalinstrumental"] = "instrumental"

        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json().get("results", [])

        tracks = []
        for item in data:
            musicinfo = item.get("musicinfo", {}) or {}
            tags_block = musicinfo.get("tags", {}) or {}
            duration = int(item.get("duration", 0) or 0)

            if not (MIN_TRACK_DURATION <= duration <= MAX_TRACK_DURATION):
                continue

            genre_tags = []
            if isinstance(tags_block, dict):
                genres = tags_block.get("genres", [])
                if isinstance(genres, list):
                    genre_tags = [str(g).lower() for g in genres]

            audio_url = item.get("audio")
            if not audio_url:
                continue

            tracks.append({
                "id": str(item.get("id")),
                "name": item.get("name"),
                "artist": item.get("artist_name"),
                "audio_url": audio_url,
                "duration": duration,
                "tags": tags_block,
                "genre_tags": genre_tags,
                "bpm": musicinfo.get("bpm"),
                "key": musicinfo.get("key"),
            })

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