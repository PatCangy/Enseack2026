# song_classifier.py


class SongClassifier:
    def classify_song(self, features):
        tempo    = features.get("tempo",    0)
        rms      = features.get("rms",      0)
        # centroid is no longer used in the primary decision.
        # It was causing misclassification of house/lounge tracks as CALM
        # because house music naturally has high spectral centroid (bright hi-hats,
        # open synths) that pushed it above the old 2500 Hz cutoff.

        # CALM: slow tempo + genuinely quiet signal
        if tempo < 95 and rms < 0.06:
            return "CALM"

        # WARM: moderate tempo, moderate energy
        # Raised rms ceiling from 0.12 → 0.10 to be stricter about what counts as warm
        elif tempo < 115 and rms < 0.10:
            return "WARM"

        # ENERGETIC: fast tempo, high energy
        # Raised tempo ceiling slightly (130 → 132) to catch tracks that librosa
        # detects at half-tempo (e.g. 66 bpm detected when true bpm is 132)
        elif tempo < 132 and rms < 0.20:
            return "ENERGETIC"

        # HYPE: everything that exceeds the above
        return "HYPE"

    def classify_all(self, features_list):
        for song in features_list:
            song["mood"] = self.classify_song(song)
        return features_list