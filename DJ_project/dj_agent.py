# dj_agent.py

from config import MOOD_TAGS, MOOD_BPM


class DJAgent:
    def __init__(self, jamendo_client, track_cache):
        self.jamendo_client = jamendo_client
        self.track_cache = track_cache
        self.current_mood = "CALM"

    def classify_mood(self, amplitude):
        if amplitude < 0.03:
            return "CALM"
        elif amplitude < 0.08:
            return "WARM"
        elif amplitude < 0.15:
            return "ENERGETIC"
        return "HYPE"

    def score_track(self, track, mood):
        score = 0

        bpm = track.get("bpm")
        key = track.get("key")
        bpm_min, bpm_max = MOOD_BPM[mood]

        if bpm is not None and bpm_min <= bpm <= bpm_max:
            score += 3

        if key:
            score += 1

        score += 1  # base score

        return score

    def choose_next_track(self, amplitude):
        mood = self.classify_mood(amplitude)
        tags = MOOD_TAGS[mood]

        tracks = self.jamendo_client.search_tracks(tags, limit=20)
        tracks = self.track_cache.filter_unplayed(tracks)

        if not tracks:
            return mood, None

        scored = []
        for track in tracks:
            score = self.score_track(track, mood)
            scored.append((score, track))

        scored.sort(reverse=True, key=lambda x: x[0])
        best_track = scored[0][1]

        self.current_mood = mood
        return mood, best_track