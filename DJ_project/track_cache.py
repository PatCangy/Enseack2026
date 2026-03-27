# track_cache.py

import json
import os
from config import HISTORY_FILE


class TrackCache:
    def __init__(self):
        self.history_file = HISTORY_FILE
        self.history = self._load_history()

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
        recent_ids = [track["id"] for track in recent]
        return track_id in recent_ids

    def filter_unplayed(self, tracks, recent_limit=10):
        return [
            track for track in tracks
            if not self.was_played_recently(track["id"], recent_limit)
        ]

    def mark_played(self, track):
        self.history.append({
            "id": track["id"],
            "name": track["name"],
            "artist": track["artist"],
        })
        self._save_history()