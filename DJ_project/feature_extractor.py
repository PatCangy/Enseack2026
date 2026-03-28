# feature_extractor.py

import os
import json
import librosa
import numpy as np


class FeatureExtractor:
    def extract_features(self, filepath):
        """
        Analyze a single audio file and return its acoustic features.
        This is called per-track during the pre-screening phase so we can
        inject real BPM/RMS into the track dict before the agent gates it.
        """
        y, sr = librosa.load(filepath, sr=None, mono=True)

        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        rms       = float(np.mean(librosa.feature.rms(y=y)))
        centroid  = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))

        return {
            "path":      filepath,
            "tempo":     float(tempo),
            "rms":       rms,
            "centroid":  centroid,
            "bandwidth": bandwidth,
        }

    def enrich_track(self, track, filepath):
        """
        Download has already happened. Analyze the file and inject
        tempo and rms directly into the track dict so the DJ agent
        gate can use real values instead of Jamendo's missing metadata.

        Returns True if analysis succeeded, False on error.
        """
        try:
            features = self.extract_features(filepath)
            # Inject librosa BPM as the authoritative BPM —
            # overrides Jamendo's bpm field (which is almost always None)
            track["bpm"] = round(features["tempo"], 2)
            track["rms"] = features["rms"]
            track["centroid"]  = features["centroid"]
            track["bandwidth"] = features["bandwidth"]
            print(f"  [analyze] {track['name'][:40]} | bpm={track['bpm']} | rms={round(track['rms'], 4)}")
            return True
        except Exception as e:
            print(f"  [analyze error] {track.get('name', filepath)}: {e}")
            return False

    def analyze_folder(self, folder_path, output_file="song_features.json"):
        """
        Analyze all MP3s in a folder. Used after playback selection
        to write song_features.json for classification review.
        """
        features = []

        mp3_files = [f for f in os.listdir(folder_path) if f.endswith(".mp3")]

        if not mp3_files:
            print("  [extractor] No MP3 files found in", folder_path)
            return features

        for filename in mp3_files:
            filepath = os.path.join(folder_path, filename)
            try:
                song_features = self.extract_features(filepath)
                features.append(song_features)
                print(
                    f"  [extractor] {filename}"
                    f" | tempo={song_features['tempo']:.1f}"
                    f" | rms={song_features['rms']:.4f}"
                )
            except Exception as e:
                print(f"  [extractor] Error analyzing {filename}: {e}")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(features, f, indent=2)

        return features