# dj_agent.py

from config import MOOD_TAGS, MOOD_BPM, MOOD_MIN_RMS


class DJAgent:
    def __init__(self, jamendo_client, track_cache):
        self.jamendo_client = jamendo_client
        self.track_cache    = track_cache
        self.current_mood   = "CALM"
        self.energy_history = []

    # ------------------------------------------------------------------
    # Mood classification
    # ------------------------------------------------------------------

    def classify_mood_raw(self, room_energy):
        if room_energy <= 3:
            return "CALM"
        elif room_energy <= 6:
            return "WARM"
        elif room_energy <= 8:
            return "ENERGETIC"
        return "HYPE"

    def update_energy_history(self, room_energy, max_len=5):
        self.energy_history.append(room_energy)
        if len(self.energy_history) > max_len:
            self.energy_history.pop(0)

    def get_energy_trend(self):
        if len(self.energy_history) < 3:
            return "stable"
        diff = self.energy_history[-1] - self.energy_history[0]
        if diff >= 2:
            return "rising"
        elif diff <= -2:
            return "falling"
        return "stable"

    def mood_index(self, mood):
        return ["CALM", "WARM", "ENERGETIC", "HYPE"].index(mood)

    def mood_from_index(self, index):
        order = ["CALM", "WARM", "ENERGETIC", "HYPE"]
        return order[max(0, min(index, len(order) - 1))]

    def apply_trend_to_mood(self, base_mood):
        trend = self.get_energy_trend()
        idx   = self.mood_index(base_mood)
        if trend == "rising":
            idx += 1
        elif trend == "falling":
            idx -= 1
        return self.mood_from_index(idx)

    def classify_mood(self, room_energy):
        self.update_energy_history(room_energy)
        raw_mood   = self.classify_mood_raw(room_energy)
        trend_mood = self.apply_trend_to_mood(raw_mood)

        if self.current_mood == "CALM":
            if self.mood_index(trend_mood) >= self.mood_index("WARM") and room_energy >= 5:
                return "WARM"
            return "CALM"

        elif self.current_mood == "WARM":
            if self.mood_index(trend_mood) <= self.mood_index("CALM") and room_energy <= 2:
                return "CALM"
            elif self.mood_index(trend_mood) >= self.mood_index("ENERGETIC") and room_energy >= 7:
                return "ENERGETIC"
            return "WARM"

        elif self.current_mood == "ENERGETIC":
            if self.mood_index(trend_mood) <= self.mood_index("WARM") and room_energy <= 5:
                return "WARM"
            elif self.mood_index(trend_mood) >= self.mood_index("HYPE") and room_energy >= 9:
                return "HYPE"
            return "ENERGETIC"

        elif self.current_mood == "HYPE":
            if self.mood_index(trend_mood) <= self.mood_index("ENERGETIC") and room_energy <= 7:
                return "ENERGETIC"
            return "HYPE"

        return trend_mood

    # ------------------------------------------------------------------
    # Hard gate — runs AFTER librosa enrichment, not before
    # ------------------------------------------------------------------

    def _passes_hard_gates(self, track, mood):
        """
        Called after enrich_track() has injected real BPM and RMS from librosa.
        At this point bpm is never None — if enrich_track failed, the track
        was already removed from the candidate list in prototype_app.py.

        Gate 1 — BPM sanity range (55–180 BPM).
          librosa occasionally detects half-tempo or double-tempo. A track
          detected at 45 BPM is almost always a 90 BPM track at half detection.
          We correct half-tempo by doubling, and double-tempo by halving.

        Gate 2 — RMS energy floor.
          Rejects genuinely quiet/ambient tracks that slipped through the tag filter.
        """
        bpm = track.get("bpm")
        rms = track.get("rms")

        if bpm is None:
            return False

        bpm = float(bpm)

        # Correct librosa half-tempo detection (common for 4/4 dance tracks)
        if bpm < 55:
            bpm *= 2
            track["bpm"] = round(bpm, 2)

        # Correct librosa double-tempo detection
        if bpm > 180:
            bpm /= 2
            track["bpm"] = round(bpm, 2)

        # After correction, hard reject anything still out of range
        if not (55 <= bpm <= 180):
            return False

        # RMS energy floor
        if rms is not None:
            min_rms = MOOD_MIN_RMS.get(mood, 0.0)
            if float(rms) < min_rms:
                return False

        return True

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def extract_genre_tags(self, track):
        tags = track.get("tags", {})
        if isinstance(tags, dict):
            genres = tags.get("genres", [])
            if isinstance(genres, list):
                return [g.lower() for g in genres]
        return []

    def genre_continuity_score(self, track_genres, recent_genres, target_tags):
        score = 0
        for tag in target_tags:
            if tag.lower() in track_genres:
                score += 3
        for genre in track_genres:
            if genre in recent_genres:
                score += 2
        return score

    def anti_hard_switch_penalty(self, track_genres, recent_genres, target_tags):
        if not track_genres:
            return 0
        matches_recent = any(g in recent_genres for g in track_genres)
        matches_target = any(g in [t.lower() for t in target_tags] for g in track_genres)
        if recent_genres and not matches_recent and not matches_target:
            return -4
        return 0

    def transition_score(self, previous_track, current_track):
        score = 0

        prev_bpm    = previous_track.get("bpm")
        curr_bpm    = current_track.get("bpm")
        prev_key    = previous_track.get("key")
        curr_key    = current_track.get("key")
        prev_genres = previous_track.get("genre_tags", [])
        curr_genres = current_track.get("genre_tags", [])

        if prev_bpm is not None and curr_bpm is not None:
            diff = abs(float(prev_bpm) - float(curr_bpm))
            if diff <= 3:
                score += 5
            elif diff <= 6:
                score += 3
            elif diff <= 10:
                score += 1
            else:
                score -= 2

        if prev_key and curr_key and prev_key == curr_key:
            score += 3

        if prev_genres and curr_genres:
            shared = set(prev_genres) & set(curr_genres)
            score += 4 if shared else -2

        return score

    def base_score_track(self, track, mood):
        score = 0

        bpm              = track.get("bpm")
        key              = track.get("key")
        bpm_min, bpm_max = MOOD_BPM[mood]
        target_tags      = MOOD_TAGS[mood]
        recent_genres    = self.track_cache.get_recent_genres(recent_limit=5)
        track_genres     = self.extract_genre_tags(track)

        track["genre_tags"] = track_genres

        if bpm is not None:
            bpm = float(bpm)
            if bpm_min <= bpm <= bpm_max:
                score += 5
            else:
                distance = min(abs(bpm - bpm_min), abs(bpm - bpm_max))
                if distance <= 10:
                    score += 2

        if key:
            score += 1

        score += self.genre_continuity_score(track_genres, recent_genres, target_tags)
        score += self.anti_hard_switch_penalty(track_genres, recent_genres, target_tags)
        score += 1

        return score

    # ------------------------------------------------------------------
    # Main selection — BPM enrichment now happens in prototype_app.py
    # before this method is called, so all tracks here have real BPM/RMS
    # ------------------------------------------------------------------

    def choose_tracks_from_enriched(self, tracks, mood, limit=5):
        """
        Called after tracks have been downloaded and enriched by librosa.
        Applies the hard gate, scores, and returns the best ordered selection.
        """
        # Hard gate with real BPM/RMS
        passed   = [t for t in tracks if self._passes_hard_gates(t, mood)]
        rejected = len(tracks) - len(passed)
        if rejected:
            print(f"  [agent] Rejected {rejected} track(s) — BPM out of range or too quiet")
        print(f"  [agent] {len(passed)} track(s) passed the gate")

        if not passed:
            return []

        for track in passed:
            track["genre_tags"] = self.extract_genre_tags(track)

        ranked = sorted(
            [(self.base_score_track(t, mood), t) for t in passed],
            key=lambda x: x[0],
            reverse=True,
        )

        remaining = [t for _, t in ranked]
        selected  = [remaining.pop(0)]

        while remaining and len(selected) < limit:
            previous   = selected[-1]
            best_next  = None
            best_score = float("-inf")

            for candidate in remaining:
                score = self.base_score_track(candidate, mood)
                score += self.transition_score(previous, candidate)
                if score > best_score:
                    best_score = score
                    best_next  = candidate

            if best_next is None:
                break

            selected.append(best_next)
            remaining.remove(best_next)

        self.current_mood = mood
        return selected

    def classify_mood(self, room_energy):
        # kept for prototype_app.py to call before fetching
        self.update_energy_history(room_energy)
        raw_mood   = self.classify_mood_raw(room_energy)
        trend_mood = self.apply_trend_to_mood(raw_mood)

        if self.current_mood == "CALM":
            if self.mood_index(trend_mood) >= self.mood_index("WARM") and room_energy >= 5:
                return "WARM"
            return "CALM"
        elif self.current_mood == "WARM":
            if self.mood_index(trend_mood) <= self.mood_index("CALM") and room_energy <= 2:
                return "CALM"
            elif self.mood_index(trend_mood) >= self.mood_index("ENERGETIC") and room_energy >= 7:
                return "ENERGETIC"
            return "WARM"
        elif self.current_mood == "ENERGETIC":
            if self.mood_index(trend_mood) <= self.mood_index("WARM") and room_energy <= 5:
                return "WARM"
            elif self.mood_index(trend_mood) >= self.mood_index("HYPE") and room_energy >= 9:
                return "HYPE"
            return "ENERGETIC"
        elif self.current_mood == "HYPE":
            if self.mood_index(trend_mood) <= self.mood_index("ENERGETIC") and room_energy <= 7:
                return "ENERGETIC"
            return "HYPE"
        return trend_mood