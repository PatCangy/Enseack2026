# beat_detector.py
# ─────────────────────────────────────────────────────────────────────────────
# Real-time beat detector using BlackHole loopback audio capture.
#
# How it works:
#   - Captures system audio via BlackHole (device 0) in real time
#   - Computes RMS amplitude of each audio block
#   - Maintains a short rolling average of recent RMS values
#   - Fires a beat when RMS spikes above (rolling_avg × BEAT_THRESHOLD)
#   - Enforces a minimum gap between beats (MIN_BEAT_INTERVAL_MS) to avoid
#     double-triggering on a single transient
#
# Usage:
#   detector = BeatDetector(on_beat=my_callback, device=0)
#   detector.start()
#   ...
#   detector.stop()
#
# The on_beat callback is called from the audio thread — keep it fast.
# ─────────────────────────────────────────────────────────────────────────────

import time
import threading
import numpy as np
import sounddevice as sd


# ── Tuning parameters ─────────────────────────────────────────────────────────
SAMPLERATE        = 44100
BLOCKSIZE         = 1024       # smaller = more responsive (~23ms per block)
BEAT_THRESHOLD    = 1.8        # RMS must be this × rolling avg to count as beat
ROLLING_WINDOW    = 30         # number of blocks in the rolling average (~700ms)
MIN_BEAT_INTERVAL_MS = 300     # minimum ms between two beats (~200 BPM max)
SILENCE_FLOOR     = 0.005      # ignore blocks quieter than this (silence / gaps)


class BeatDetector:
    def __init__(self, on_beat, device=0):
        """
        Args:
            on_beat : callable — called with no arguments each time a beat is detected
            device  : int — sounddevice input device index (BlackHole = 0)
        """
        self.on_beat   = on_beat
        self.device    = device
        self.stream    = None
        self.running   = False

        self._history       = []          # rolling RMS history
        self._last_beat_ms  = 0           # timestamp of last fired beat

    # ── Audio callback (runs on audio thread) ─────────────────────────────────

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"  [beat] audio status: {status}")

        # Compute RMS of this block
        rms = float(np.sqrt(np.mean(indata ** 2)))

        # Skip silence
        if rms < SILENCE_FLOOR:
            return

        # Update rolling average
        self._history.append(rms)
        if len(self._history) > ROLLING_WINDOW:
            self._history.pop(0)

        if len(self._history) < 4:
            return  # need a few samples before we can detect anything meaningful

        rolling_avg = float(np.mean(self._history))

        # Beat condition: current RMS is significantly above the recent average
        if rms > rolling_avg * BEAT_THRESHOLD:
            now_ms = int(time.time() * 1000)
            if now_ms - self._last_beat_ms >= MIN_BEAT_INTERVAL_MS:
                self._last_beat_ms = now_ms
                try:
                    self.on_beat()
                except Exception as e:
                    print(f"  [beat] on_beat callback error: {e}")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            return
        self.running = True

        try:
            self.stream = sd.InputStream(
                device=self.device,
                channels=2,              # BlackHole is stereo
                samplerate=SAMPLERATE,
                blocksize=BLOCKSIZE,
                dtype="float32",
                callback=self._audio_callback,
            )
            self.stream.start()
            print(f"  [beat] Beat detector started on device {self.device} (BlackHole)")
        except Exception as e:
            self.running = False
            print(f"  [beat] Could not open audio device {self.device}: {e}")
            print(f"  [beat] Make sure BlackHole is installed and set as output.")

    def stop(self):
        self.running = False
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        print("  [beat] Beat detector stopped")