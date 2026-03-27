# audio_capture.py

import threading
import time
import numpy as np
import sounddevice as sd


class AudioCapture:
    def __init__(self, interval=0.05, samplerate=44100):
        self.interval = interval
        self.samplerate = samplerate
        self.amplitude = 0.0
        self.running = False
        self.thread = None

    def _capture_loop(self):
        frames = int(self.samplerate * self.interval)

        while self.running:
            try:
                data = sd.rec(frames, samplerate=self.samplerate, channels=1, dtype="float32")
                sd.wait()
                rms = np.sqrt(np.mean(np.square(data)))
                self.amplitude = float(rms)
            except Exception:
                self.amplitude = 0.0

            time.sleep(self.interval)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def get_amplitude(self):
        return self.amplitude