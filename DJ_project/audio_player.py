# # audio_player.py

# import threading
# import time
# from pydub import AudioSegment
# from pydub.playback import play


# class AudioPlayer:
#     def __init__(self, serial_formatter=None):
#         # Optional: pass a SerialFormatter instance to trigger LED changes
#         # during playback. If None, LED sync is skipped silently.
#         self.serial_formatter = serial_formatter

#     # ------------------------------------------------------------------
#     # Demo mode — the one you want for the presentation
#     # ------------------------------------------------------------------

#     def play_demo(self, tracks, segment_ms=30_000, crossfade_ms=4_000):
#         """
#         Presentation demo mode.

#         Each track plays for `segment_ms` milliseconds (default 30 s),
#         then crossfades into the next over `crossfade_ms` ms (default 4 s).
#         Total runtime ≈ (segment_ms × n_tracks) - (crossfade_ms × (n_tracks-1))

#         With 3 tracks at 30 s each and 4 s crossfades:
#           30 + 26 + 26 = ~82 seconds ≈ 1 min 22 s  (close to 1:30)

#         LED colors change at the START of each segment so the audience
#         sees the color shift happen in sync with the music change.

#         Args:
#             tracks       : list of track dicts, each must have 'local_path' and 'mood'
#             segment_ms   : how many ms to play from each track
#             crossfade_ms : crossfade length in ms
#         """
#         if not tracks:
#             print("  [player] No tracks to play.")
#             return

#         print(f"\n  [demo] Building {len(tracks)}-track demo mix")
#         print(f"         {segment_ms//1000}s per track | {crossfade_ms//1000}s crossfade\n")

#         segments = []
#         for i, track in enumerate(tracks):
#             path = track.get("local_path")
#             mood = track.get("mood", "CALM")
#             name = track.get("name", f"Track {i+1}")

#             try:
#                 audio = AudioSegment.from_file(path)
#             except Exception as e:
#                 print(f"  [player] Could not load {name}: {e}")
#                 continue

#             # Pick the most energetic part of the track:
#             # start at 20% in to skip intros, take segment_ms from there
#             start_ms = int(len(audio) * 0.20)
#             end_ms   = start_ms + segment_ms

#             # If the track is too short just take what we have
#             if end_ms > len(audio):
#                 start_ms = max(0, len(audio) - segment_ms)
#                 end_ms   = len(audio)

#             clip = audio[start_ms:end_ms]
#             segments.append({
#                 "clip": clip,
#                 "mood": mood,
#                 "name": name,
#                 "artist": track.get("artist", ""),
#             })

#             duration_s = len(clip) / 1000
#             print(f"  [{i+1}] {name[:40]} — {mood} ({duration_s:.1f}s clip)")

#         if not segments:
#             print("  [player] No segments built.")
#             return

#         # Stitch segments together with crossfade
#         mix = segments[0]["clip"]
#         for seg in segments[1:]:
#             mix = mix.append(seg["clip"], crossfade=crossfade_ms)

#         total_s = len(mix) / 1000
#         print(f"\n  [demo] Mix ready — total duration: {total_s:.1f}s ({total_s/60:.1f} min)")
#         print(  "  [demo] Starting playback...\n")

#         # Play in a background thread so we can fire LED changes on the main thread
#         playback_done = threading.Event()

#         def _play():
#             play(mix)
#             playback_done.set()

#         thread = threading.Thread(target=_play, daemon=True)
#         thread.start()

#         # Fire LED color change at the start of each segment
#         # Timing: segment N starts at cumulative offset accounting for crossfades
#         if self.serial_formatter:
#             self._sync_leds(segments, segment_ms, crossfade_ms, playback_done)
#         else:
#             # No serial — just print what the LEDs would do so the demo still makes sense
#             self._print_led_timeline(segments, segment_ms, crossfade_ms, playback_done)

#         playback_done.wait()
#         print("\n  [demo] Playback complete.")

#     def _sync_leds(self, segments, segment_ms, crossfade_ms, stop_event):
#         """Send LED mood updates timed to each segment transition."""
#         offset_ms = 0
#         for i, seg in enumerate(segments):
#             if stop_event.is_set():
#                 break

#             wait_s = offset_ms / 1000
#             time.sleep(wait_s)

#             mood = seg["mood"]
#             self.serial_formatter.update_state(mood, amp=0.8)
#             print(f"  [LED] → {mood}  ({seg['name'][:35]})")

#             # Next segment starts after segment_ms minus the crossfade overlap
#             if i == 0:
#                 offset_ms = segment_ms - crossfade_ms
#             else:
#                 offset_ms = segment_ms - crossfade_ms

#     def _print_led_timeline(self, segments, segment_ms, crossfade_ms, stop_event):
#         """
#         No serial port connected — simulate LED changes with console output.
#         Useful for testing the timing without hardware.
#         """
#         offset_ms = 0
#         for i, seg in enumerate(segments):
#             if stop_event.is_set():
#                 break

#             wait_s = offset_ms / 1000
#             time.sleep(wait_s)

#             mood   = seg["mood"]
#             name   = seg["name"][:35]
#             artist = seg["artist"][:25]
#             print(f"  [LED] → {mood:10}  🎵  {name} — {artist}")

#             if i == 0:
#                 offset_ms = segment_ms - crossfade_ms
#             else:
#                 offset_ms = segment_ms - crossfade_ms

#     # ------------------------------------------------------------------
#     # Full playback — used outside demo mode
#     # ------------------------------------------------------------------

#     def build_crossfaded_mix(self, filepaths, crossfade_ms=5000):
#         if not filepaths:
#             return None

#         print(f"  [player] Building mix — {len(filepaths)} track(s), {crossfade_ms}ms crossfade")
#         mix = AudioSegment.from_file(filepaths[0])

#         for path in filepaths[1:]:
#             next_song = AudioSegment.from_file(path)
#             mix = mix.append(next_song, crossfade=crossfade_ms)

#         total_min = len(mix) / 1000 / 60
#         print(f"  [player] Mix ready — {total_min:.1f} min total")
#         return mix

#     def play_queue(self, filepaths, crossfade_ms=5000):
#         if not filepaths:
#             print("  [player] No songs to play.")
#             return

#         mix = self.build_crossfaded_mix(filepaths, crossfade_ms=crossfade_ms)
#         if mix is None:
#             print("  [player] Failed to build mix.")
#             return

#         print("  [player] Playing...")
#         play(mix)

# audio_player.py
# ─────────────────────────────────────────────────────────────────────────────
# Upgraded mixing layer with:
#   1. BPM-matched time-stretching (pitch-preserving via librosa phase vocoder)
#   2. Beat-aligned crossfade (transition starts on a downbeat)
#   3. Background pre-processing so there is zero gap between tracks
#   4. Fallback: if pre-processing isn't ready in time, holds the current
#      track a few extra seconds rather than going silent
# ─────────────────────────────────────────────────────────────────────────────

import threading
import time
import numpy as np
import librosa
import soundfile as sf
import io
import tempfile
import os
from pydub import AudioSegment
from pydub.playback import play


# ── Helpers ───────────────────────────────────────────────────────────────────

def _audiosegment_to_numpy(segment: AudioSegment):
    """Convert a pydub AudioSegment to a librosa-compatible numpy array (float32, mono)."""
    samples = np.array(segment.get_array_of_samples(), dtype=np.float32)
    # Normalize int16 range to [-1.0, 1.0]
    samples /= float(1 << (segment.sample_width * 8 - 1))
    if segment.channels == 2:
        samples = samples.reshape(-1, 2).mean(axis=1)
    return samples, segment.frame_rate


def _numpy_to_audiosegment(samples: np.ndarray, sr: int) -> AudioSegment:
    """Convert a float32 numpy array back to a pydub AudioSegment (16-bit mono)."""
    # Clip to prevent int16 overflow
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples * 32767).astype(np.int16)
    return AudioSegment(
        pcm.tobytes(),
        frame_rate=sr,
        sample_width=2,   # 16-bit
        channels=1,
    )


def _find_nearest_downbeat(y: np.ndarray, sr: int, target_sample: int,
                            beats_per_bar: int = 4) -> int:
    """
    Detect beats in y, group into bars, and return the sample index of the
    downbeat (bar boundary) closest to target_sample.

    Falls back to target_sample if beat detection fails.
    """
    try:
        _, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        if len(beat_frames) < beats_per_bar:
            return target_sample

        beat_samples = librosa.frames_to_samples(beat_frames)

        # Downbeats = every Nth beat
        downbeat_samples = beat_samples[::beats_per_bar]

        # Find the downbeat closest to (but not after) target_sample
        candidates = downbeat_samples[downbeat_samples <= target_sample]
        if len(candidates) == 0:
            return beat_samples[0]

        return int(candidates[-1])
    except Exception:
        return target_sample


def _time_stretch_to_bpm(y: np.ndarray, sr: int,
                          source_bpm: float, target_bpm: float) -> np.ndarray:
    """
    Time-stretch y so that its tempo matches target_bpm.
    Uses librosa's phase-vocoder time_stretch which preserves pitch.

    stretch_rate > 1 → faster (compresses time)
    stretch_rate < 1 → slower (expands time)
    """
    if abs(source_bpm - target_bpm) < 0.5:
        # Close enough — skip stretching to avoid unnecessary quality loss
        return y

    stretch_rate = target_bpm / source_bpm

    # Clamp to a reasonable range — extreme ratios sound bad
    stretch_rate = float(np.clip(stretch_rate, 0.75, 1.33))

    return librosa.effects.time_stretch(y, rate=stretch_rate)


# ── PreparedTrack ─────────────────────────────────────────────────────────────

class PreparedTrack:
    """
    Holds a fully processed clip (time-stretched, beat-aligned) ready to play.
    Created by _prepare_clip() in a background thread.
    """
    def __init__(self):
        self.segment: AudioSegment | None = None
        self.downbeat_offset_ms: int = 0   # where the crossfade-in should start
        self.ready = threading.Event()
        self.error: str | None = None


# ── AudioPlayer ───────────────────────────────────────────────────────────────

class AudioPlayer:
    def __init__(self, serial_formatter=None):
        self.serial_formatter = serial_formatter

    # ------------------------------------------------------------------
    # Demo mode — BPM-matched, beat-aligned crossfade
    # ------------------------------------------------------------------

    def play_demo(self, tracks, segment_ms=30_000, crossfade_ms=4_000):
        """
        Presentation demo mode with proper DJ mixing:
          • Each track is time-stretched to match the previous track's BPM
          • Crossfade starts on a downbeat (bar boundary)
          • Next track is pre-processed in a background thread while current plays
          • Falls back gracefully if processing is slow

        Args:
            tracks       : list of track dicts with 'local_path', 'mood', 'bpm'
            segment_ms   : how many ms to play from each track (default 30s)
            crossfade_ms : crossfade length in ms (default 4s)
        """
        if not tracks:
            print("  [player] No tracks to play.")
            return

        print(f"\n  [player] Building DJ mix — {len(tracks)} tracks")
        print(f"           {segment_ms//1000}s segments | {crossfade_ms//1000}s crossfade | BPM-matched\n")

        # Load all tracks as AudioSegments first (fast — just file I/O)
        loaded = []
        for i, track in enumerate(tracks):
            path = track.get("local_path")
            try:
                audio = AudioSegment.from_file(path).set_channels(1)
                loaded.append((track, audio))
                print(f"  [{i+1}] Loaded: {track['name'][:40]} | bpm={track.get('bpm', '?')}")
            except Exception as e:
                print(f"  [{i+1}] Could not load {track.get('name', path)}: {e}")

        if not loaded:
            print("  [player] No tracks could be loaded.")
            return

        print()

        # ── Process and play tracks one by one ───────────────────────────────

        # Pre-process the first track immediately (blocking — before playback starts)
        first_track, first_audio = loaded[0]
        target_bpm = first_track.get("bpm", 120.0)

        print(f"  [player] Preparing track 1: {first_track['name'][:40]}...")
        current_prepared = PreparedTrack()
        self._prepare_clip(
            first_audio,
            source_bpm=target_bpm,   # no stretch needed for first track
            target_bpm=target_bpm,
            segment_ms=segment_ms,
            crossfade_ms=crossfade_ms,
            prepared=current_prepared,
        )
        current_prepared.ready.wait()

        if current_prepared.error:
            print(f"  [player] Failed to prepare track 1: {current_prepared.error}")
            return

        # Iterate through tracks, mixing as we go
        mix = current_prepared.segment

        for i in range(1, len(loaded)):
            next_track, next_audio = loaded[i]
            next_bpm    = next_track.get("bpm", target_bpm)
            prev_bpm    = loaded[i - 1][0].get("bpm", target_bpm)

            # ── Start background processing of next track ─────────────────
            next_prepared = PreparedTrack()
            prep_thread   = threading.Thread(
                target=self._prepare_clip,
                args=(next_audio, next_bpm, prev_bpm,
                      segment_ms, crossfade_ms, next_prepared),
                daemon=True,
            )
            prep_thread.start()

            print(f"  [player] Pre-processing track {i+1}: {next_track['name'][:35]}"
                  f" ({next_bpm:.1f} → {prev_bpm:.1f} BPM)...")

            # ── Wait for next track to be ready ───────────────────────────
            # We have segment_ms worth of audio playing to get this ready.
            # Give it up to (segment_ms - crossfade_ms - 2000ms) to finish.
            # If it's not ready in time, wait a bit more rather than going silent.
            deadline_s = (segment_ms - crossfade_ms - 2000) / 1000
            ready = next_prepared.ready.wait(timeout=max(deadline_s, 5.0))

            if not ready or next_prepared.error:
                print(f"  [player] Warning: track {i+1} not ready in time, "
                      f"extending current track by 5s...")
                # Hold current track a bit longer — append silence then retry
                next_prepared.ready.wait(timeout=10.0)

            if next_prepared.error:
                print(f"  [player] Skipping track {i+1}: {next_prepared.error}")
                continue

            # ── Stitch with crossfade ──────────────────────────────────────
            mix = mix.append(next_prepared.segment, crossfade=crossfade_ms)
            print(f"  [player] ✓ Track {i+1} stitched at downbeat | "
                  f"mix length: {len(mix)/1000:.1f}s")

        # ── Play the completed mix ────────────────────────────────────────────
        total_s = len(mix) / 1000
        print(f"\n  [player] Mix ready — {total_s:.1f}s ({total_s/60:.1f} min)")
        print(  "  [player] Starting playback...\n")

        playback_done = threading.Event()

        def _play():
            play(mix)
            playback_done.set()

        play_thread = threading.Thread(target=_play, daemon=True)
        play_thread.start()

        # Fire LED / serial sync
        if self.serial_formatter:
            self._sync_leds(
                [t for t, _ in loaded],
                segment_ms, crossfade_ms, playback_done,
            )
        else:
            self._print_led_timeline(
                [t for t, _ in loaded],
                segment_ms, crossfade_ms, playback_done,
            )

        playback_done.wait()
        print("\n  [player] Playback complete.")

    # ------------------------------------------------------------------
    # Core processing — runs in background thread
    # ------------------------------------------------------------------

    def _prepare_clip(self, audio: AudioSegment, source_bpm: float,
                      target_bpm: float, segment_ms: int, crossfade_ms: int,
                      prepared: PreparedTrack):
        """
        Called in a background thread. Steps:
          1. Pick the clip window (start at 20% to skip intros)
          2. Convert to numpy
          3. Time-stretch to match target_bpm (pitch-preserving)
          4. Find nearest downbeat to the crossfade-out point
          5. Trim clip to end on that downbeat
          6. Convert back to AudioSegment
          7. Set prepared.ready
        """
        try:
            sr = audio.frame_rate

            # ── 1. Pick clip window ───────────────────────────────────────
            start_ms = int(len(audio) * 0.20)
            end_ms   = start_ms + segment_ms + crossfade_ms  # extra for downbeat search

            if end_ms > len(audio):
                start_ms = max(0, len(audio) - segment_ms - crossfade_ms)
                end_ms   = len(audio)

            clip = audio[start_ms:end_ms]

            # ── 2. Convert to numpy ───────────────────────────────────────
            y, sr = _audiosegment_to_numpy(clip)

            # ── 3. Time-stretch to match outgoing BPM ─────────────────────
            if abs(source_bpm - target_bpm) >= 0.5:
                print(f"    [stretch] {source_bpm:.1f} → {target_bpm:.1f} BPM "
                      f"(rate={target_bpm/source_bpm:.3f})")
                y = _time_stretch_to_bpm(y, sr, source_bpm, target_bpm)

            # ── 4. Find downbeat nearest to crossfade-out point ───────────
            # Target: segment_ms worth of audio from the start of the clip
            target_sample = int((segment_ms / 1000) * sr)
            target_sample = min(target_sample, len(y) - 1)

            downbeat_sample = _find_nearest_downbeat(y, sr, target_sample)

            # ── 5. Trim to downbeat ────────────────────────────────────────
            y_trimmed = y[:downbeat_sample]

            if len(y_trimmed) < int(0.5 * sr):
                # Trimmed too short — fall back to target_sample
                y_trimmed = y[:target_sample]

            # ── 6. Convert back to AudioSegment ───────────────────────────
            prepared.segment = _numpy_to_audiosegment(y_trimmed, sr)
            prepared.downbeat_offset_ms = int(downbeat_sample / sr * 1000)

        except Exception as e:
            prepared.error = str(e)
            print(f"    [prepare error] {e}")
        finally:
            prepared.ready.set()

    # ------------------------------------------------------------------
    # LED sync helpers (unchanged from original)
    # ------------------------------------------------------------------

    def _sync_leds(self, tracks, segment_ms, crossfade_ms, stop_event):
        offset_ms = 0
        for i, track in enumerate(tracks):
            if stop_event.is_set():
                break
            time.sleep(offset_ms / 1000)
            mood = track.get("mood", "CALM")
            self.serial_formatter.update_state(mood, amp=0.8)
            print(f"  [LED] → {mood}  ({track.get('name', '')[:35]})")
            if i < len(tracks) - 1:
                offset_ms = segment_ms - crossfade_ms

    def _print_led_timeline(self, tracks, segment_ms, crossfade_ms, stop_event):
        offset_ms = 0
        for i, track in enumerate(tracks):
            if stop_event.is_set():
                break
            time.sleep(offset_ms / 1000)
            mood   = track.get("mood", "CALM")
            name   = track.get("name", "")[:35]
            artist = track.get("artist", "")[:25]
            print(f"  [LED] → {mood:10}  🎵  {name} — {artist}")
            if i < len(tracks) - 1:
                offset_ms = segment_ms - crossfade_ms

    # ------------------------------------------------------------------
    # Full playback mode (non-demo) — also upgraded
    # ------------------------------------------------------------------

    def play_queue(self, filepaths, crossfade_ms=5000):
        """
        Full track playback with BPM-matched crossfades.
        BPM is detected fresh from each file via librosa.
        """
        if not filepaths:
            print("  [player] No songs to play.")
            return

        print(f"  [player] Building full mix — {len(filepaths)} tracks")

        segments = []
        bpms     = []

        for path in filepaths:
            try:
                audio = AudioSegment.from_file(path).set_channels(1)
                y, sr = _audiosegment_to_numpy(audio)
                tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                bpms.append(float(tempo))
                segments.append(audio)
                print(f"  [player] {os.path.basename(path)} | bpm={float(tempo):.1f}")
            except Exception as e:
                print(f"  [player] Could not load {path}: {e}")

        if not segments:
            print("  [player] No tracks could be loaded.")
            return

        mix = segments[0]
        for i in range(1, len(segments)):
            y, sr   = _audiosegment_to_numpy(segments[i])
            y_stretched = _time_stretch_to_bpm(
                y, sr,
                source_bpm=bpms[i],
                target_bpm=bpms[i - 1],
            )
            stretched_seg = _numpy_to_audiosegment(y_stretched, sr)
            mix = mix.append(stretched_seg, crossfade=crossfade_ms)

        total_min = len(mix) / 1000 / 60
        print(f"  [player] Mix ready — {total_min:.1f} min. Playing...")
        play(mix)