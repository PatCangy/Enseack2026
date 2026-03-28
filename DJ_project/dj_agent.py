from config import MOOD_TAGS, MOOD_BPM, MOOD_MIN_RMS


class DJAgent:
    def __init__(self, jamendo_client, track_cache):
        self.jamendo_client = jamendo_client
        self.track_cache = track_cache
        self.current_mood = "CALM"
        self.energy_history = []

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _safe_float(self, value, default=None):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def extract_genre_tags(self, track):
        # First try direct genre_tags
        direct_tags = track.get("genre_tags", [])
        if isinstance(direct_tags, list) and direct_tags:
            return [str(tag).lower() for tag in direct_tags]

        # Then try Jamendo nested tags
        tags = track.get("tags", {})
        if isinstance(tags, dict):
            genres = tags.get("genres", [])
            if isinstance(genres, list):
                return [str(g).lower() for g in genres]

        return []

    def target_bpm_center(self, mood):
        bpm_min, bpm_max = MOOD_BPM[mood]
        return (bpm_min + bpm_max) / 2

    # ------------------------------------------------------------
    # 1) Mood from room energy
    # ------------------------------------------------------------

    def classify_mood(self, room_energy):
        """
        Direct mapping from room energy to target mood.
        This is what you want for the prototype:
        1-3  -> CALM
        4-6  -> WARM
        7-8  -> ENERGETIC
        9-10 -> HYPE
        """
        room_energy = max(1, min(10, int(room_energy)))

        if room_energy <= 3:
            mood = "CALM"
        elif room_energy <= 6:
            mood = "WARM"
        elif room_energy <= 8:
            mood = "ENERGETIC"
        else:
            mood = "HYPE"

        self.current_mood = mood
        self.energy_history.append(room_energy)
        if len(self.energy_history) > 5:
            self.energy_history.pop(0)

        return mood

    # ------------------------------------------------------------
    # 2) Hard gate
    # ------------------------------------------------------------

    def _passes_hard_gates(self, track, mood):
        bpm = self._safe_float(track.get("bpm"))
        rms = self._safe_float(track.get("rms"))

        if bpm is None:
            return False

        # Fix common half-tempo detection
        if bpm < 55:
            bpm *= 2

        # Fix common double-tempo detection
        if bpm > 180:
            bpm /= 2

        track["bpm"] = round(bpm, 2)

        # Reject weird BPM values
        if not (55 <= bpm <= 180):
            return False

        # Reject tracks that are too quiet for the target mood
        min_rms = MOOD_MIN_RMS.get(mood, 0.0)
        if rms is None or rms < min_rms:
            return False

        track["rms"] = rms
        return True

    def _fits_target_mood_strictly(self, track, mood):
        """
        Strict mood check:
        Prefer tracks inside the target BPM range.
        """
        bpm = self._safe_float(track.get("bpm"))
        if bpm is None:
            return False

        bpm_min, bpm_max = MOOD_BPM[mood]
        return bpm_min <= bpm <= bpm_max

    # ------------------------------------------------------------
    # 3) Scoring: how well a track fits the target mood
    # ------------------------------------------------------------

    def mood_fit_score(self, track, mood):
        score = 0

        bpm = self._safe_float(track.get("bpm"))
        rms = self._safe_float(track.get("rms"), 0.0)
        key = track.get("key")
        target_tags = [tag.lower() for tag in MOOD_TAGS[mood]]
        track_genres = self.extract_genre_tags(track)
        recent_genres = self.track_cache.get_recent_genres(recent_limit=5)

        track["genre_tags"] = track_genres

        # BPM score: strong preference for target mood BPM
        if bpm is not None:
            bpm_min, bpm_max = MOOD_BPM[mood]
            bpm_center = self.target_bpm_center(mood)

            if bpm_min <= bpm <= bpm_max:
                score += 10
            else:
                distance = abs(bpm - bpm_center)
                if distance <= 5:
                    score += 6
                elif distance <= 10:
                    score += 3
                elif distance <= 15:
                    score += 1
                else:
                    score -= 4

        # Genre score: reward tags that match the target mood
        for genre in track_genres:
            if genre in target_tags:
                score += 4

        # Small continuity bonus with recent history
        for genre in track_genres:
            if genre in recent_genres:
                score += 1

        # RMS bonus: stronger moods should prefer stronger tracks
        min_rms = MOOD_MIN_RMS.get(mood, 0.0)
        if rms >= min_rms:
            score += 2

        # Small bonus if key exists
        if key:
            score += 1

        return score

    # ------------------------------------------------------------
    # 4) Scoring: how similar two tracks are
    # ------------------------------------------------------------

    def similarity_score(self, track_a, track_b):
        score = 0

        bpm_a = self._safe_float(track_a.get("bpm"))
        bpm_b = self._safe_float(track_b.get("bpm"))
        key_a = track_a.get("key")
        key_b = track_b.get("key")
        genres_a = set(track_a.get("genre_tags", []))
        genres_b = set(track_b.get("genre_tags", []))

        # BPM similarity
        if bpm_a is not None and bpm_b is not None:
            diff = abs(bpm_a - bpm_b)
            if diff <= 2:
                score += 6
            elif diff <= 5:
                score += 4
            elif diff <= 8:
                score += 2
            elif diff > 15:
                score -= 3

        # Key similarity
        if key_a and key_b and key_a == key_b:
            score += 3

        # Genre similarity
        shared_genres = genres_a & genres_b
        score += len(shared_genres) * 4

        if genres_a and genres_b and not shared_genres:
            score -= 2

        return score

    # ------------------------------------------------------------
    # 5) Main selection
    # ------------------------------------------------------------

    def choose_tracks_from_enriched(self, tracks, mood, limit=5):
        # Step 1: hard gate
        passed = [t for t in tracks if self._passes_hard_gates(t, mood)]
        rejected = len(tracks) - len(passed)

        if rejected:
            print(f"  [agent] Rejected {rejected} track(s) — BPM out of range or too quiet")
        print(f"  [agent] {len(passed)} track(s) passed the hard gate")

        if not passed:
            return []

        # Add genre tags now so later scoring can use them
        for track in passed:
            track["genre_tags"] = self.extract_genre_tags(track)

        # Step 2: prefer tracks that strictly fit the target mood BPM
        strict_candidates = [t for t in passed if self._fits_target_mood_strictly(t, mood)]

        if strict_candidates:
            pool = strict_candidates
            print(f"  [agent] {len(pool)} track(s) strictly match target mood {mood}")
        else:
            pool = passed
            print(f"  [agent] No strict {mood} matches, using best available fallback tracks")

        # Step 3: rank by mood fit
        ranked = sorted(
            pool,
            key=lambda t: self.mood_fit_score(t, mood),
            reverse=True
        )

        if not ranked:
            return []

        # Step 4: choose first seed track = strongest match to target mood
        selected = [ranked.pop(0)]

        # Step 5: choose next tracks that both:
        # - still fit the target mood
        # - are similar to the selected tracks
        while ranked and len(selected) < limit:
            best_track = None
            best_score = float("-inf")

            for candidate in ranked:
                score = self.mood_fit_score(candidate, mood)

                # Similar to first selected track
                score += self.similarity_score(selected[0], candidate)

                # Similar to the most recent selected track
                score += self.similarity_score(selected[-1], candidate)

                # Small bonus if similar to the whole selected set
                for prev in selected[1:-1]:
                    score += 0.5 * self.similarity_score(prev, candidate)

                if score > best_score:
                    best_score = score
                    best_track = candidate

            if best_track is None:
                break

            selected.append(best_track)
            ranked.remove(best_track)

        # Save the target mood on each track
        for track in selected:
            track["target_mood"] = mood

        return selected