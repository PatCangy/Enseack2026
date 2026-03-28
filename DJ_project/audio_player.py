# audio_player.py

import threading
import time
from pydub import AudioSegment
from pydub.playback import play


class AudioPlayer:
    def __init__(self, serial_formatter=None):
        # Optional: pass a SerialFormatter instance to trigger LED changes
        # during playback. If None, LED sync is skipped silently.
        self.serial_formatter = serial_formatter

    # ------------------------------------------------------------------
    # Demo mode — the one you want for the presentation
    # ------------------------------------------------------------------

    def play_demo(self, tracks, segment_ms=30_000, crossfade_ms=4_000):
        """
        Presentation demo mode.

        Each track plays for `segment_ms` milliseconds (default 30 s),
        then crossfades into the next over `crossfade_ms` ms (default 4 s).
        Total runtime ≈ (segment_ms × n_tracks) - (crossfade_ms × (n_tracks-1))

        With 3 tracks at 30 s each and 4 s crossfades:
          30 + 26 + 26 = ~82 seconds ≈ 1 min 22 s  (close to 1:30)

        LED colors change at the START of each segment so the audience
        sees the color shift happen in sync with the music change.

        Args:
            tracks       : list of track dicts, each must have 'local_path' and 'mood'
            segment_ms   : how many ms to play from each track
            crossfade_ms : crossfade length in ms
        """
        if not tracks:
            print("  [player] No tracks to play.")
            return

        print(f"\n  [demo] Building {len(tracks)}-track demo mix")
        print(f"         {segment_ms//1000}s per track | {crossfade_ms//1000}s crossfade\n")

        segments = []
        for i, track in enumerate(tracks):
            path = track.get("local_path")
            mood = track.get("mood", "CALM")
            name = track.get("name", f"Track {i+1}")

            try:
                audio = AudioSegment.from_file(path)
            except Exception as e:
                print(f"  [player] Could not load {name}: {e}")
                continue

            # Pick the most energetic part of the track:
            # start at 20% in to skip intros, take segment_ms from there
            start_ms = int(len(audio) * 0.20)
            end_ms   = start_ms + segment_ms

            # If the track is too short just take what we have
            if end_ms > len(audio):
                start_ms = max(0, len(audio) - segment_ms)
                end_ms   = len(audio)

            clip = audio[start_ms:end_ms]
            segments.append({
                "clip": clip,
                "mood": mood,
                "name": name,
                "artist": track.get("artist", ""),
            })

            duration_s = len(clip) / 1000
            print(f"  [{i+1}] {name[:40]} — {mood} ({duration_s:.1f}s clip)")

        if not segments:
            print("  [player] No segments built.")
            return

        # Stitch segments together with crossfade
        mix = segments[0]["clip"]
        for seg in segments[1:]:
            mix = mix.append(seg["clip"], crossfade=crossfade_ms)

        total_s = len(mix) / 1000
        print(f"\n  [demo] Mix ready — total duration: {total_s:.1f}s ({total_s/60:.1f} min)")
        print(  "  [demo] Starting playback...\n")

        # Play in a background thread so we can fire LED changes on the main thread
        playback_done = threading.Event()

        def _play():
            play(mix)
            playback_done.set()

        thread = threading.Thread(target=_play, daemon=True)
        thread.start()

        # Fire LED color change at the start of each segment
        # Timing: segment N starts at cumulative offset accounting for crossfades
        if self.serial_formatter:
            self._sync_leds(segments, segment_ms, crossfade_ms, playback_done)
        else:
            # No serial — just print what the LEDs would do so the demo still makes sense
            self._print_led_timeline(segments, segment_ms, crossfade_ms, playback_done)

        playback_done.wait()
        print("\n  [demo] Playback complete.")

    def _sync_leds(self, segments, segment_ms, crossfade_ms, stop_event):
        """Send LED mood updates timed to each segment transition."""
        offset_ms = 0
        for i, seg in enumerate(segments):
            if stop_event.is_set():
                break

            wait_s = offset_ms / 1000
            time.sleep(wait_s)

            mood = seg["mood"]
            self.serial_formatter.update_state(mood, amp=0.8)
            print(f"  [LED] → {mood}  ({seg['name'][:35]})")

            # Next segment starts after segment_ms minus the crossfade overlap
            if i == 0:
                offset_ms = segment_ms - crossfade_ms
            else:
                offset_ms = segment_ms - crossfade_ms

    def _print_led_timeline(self, segments, segment_ms, crossfade_ms, stop_event):
        """
        No serial port connected — simulate LED changes with console output.
        Useful for testing the timing without hardware.
        """
        offset_ms = 0
        for i, seg in enumerate(segments):
            if stop_event.is_set():
                break

            wait_s = offset_ms / 1000
            time.sleep(wait_s)

            mood   = seg["mood"]
            name   = seg["name"][:35]
            artist = seg["artist"][:25]
            print(f"  [LED] → {mood:10}  🎵  {name} — {artist}")

            if i == 0:
                offset_ms = segment_ms - crossfade_ms
            else:
                offset_ms = segment_ms - crossfade_ms

    # ------------------------------------------------------------------
    # Full playback — used outside demo mode
    # ------------------------------------------------------------------

    def build_crossfaded_mix(self, filepaths, crossfade_ms=5000):
        if not filepaths:
            return None

        print(f"  [player] Building mix — {len(filepaths)} track(s), {crossfade_ms}ms crossfade")
        mix = AudioSegment.from_file(filepaths[0])

        for path in filepaths[1:]:
            next_song = AudioSegment.from_file(path)
            mix = mix.append(next_song, crossfade=crossfade_ms)

        total_min = len(mix) / 1000 / 60
        print(f"  [player] Mix ready — {total_min:.1f} min total")
        return mix

    def play_queue(self, filepaths, crossfade_ms=5000):
        if not filepaths:
            print("  [player] No songs to play.")
            return

        mix = self.build_crossfaded_mix(filepaths, crossfade_ms=crossfade_ms)
        if mix is None:
            print("  [player] Failed to build mix.")
            return

        print("  [player] Playing...")
        play(mix)