# track_cache.py

import json
import os
from config import HISTORY_FILE


class TrackCache:
    def __init__(self):
        self.history_file = HISTORY_FILE
        self.history      = self._load_history()

    def _load_history(self):
        if not os.path.exists(self.history_file):
            return []
        with open(self.history_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_history(self):
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)

    def was_played_recently(self, track_id, recent_limit=10):
        recent = self.history[-recent_limit:]
        return str(track_id) in [str(t["id"]) for t in recent]

    def filter_unplayed(self, tracks, recent_limit=10):
        return [t for t in tracks if not self.was_played_recently(t["id"], recent_limit)]

    def get_recent_genres(self, recent_limit=5):
        recent = self.history[-recent_limit:]
        genres = []
        for track in recent:
            for genre in track.get("genre_tags", []):
                genres.append(genre.lower())
        return genres

    def mark_played(self, track):
        self.history.append({
            "id":         str(track["id"]),
            "name":       track["name"],
            "artist":     track["artist"],
            "genre_tags": track.get("genre_tags", []),
        })
        self._save_history()