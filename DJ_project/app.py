# app.py

import time
from jamendo_client import JamendoClient
from track_cache import TrackCache
from audio_capture import AudioCapture
from dj_agent import DJAgent
from serial_formatter import SerialFormatter
from mixxx_bridge import MixxxBridge


def main():
    jamendo = JamendoClient()
    cache = TrackCache()
    audio = AudioCapture()
    agent = DJAgent(jamendo, cache)
    serial_out = SerialFormatter()
    mixxx = MixxxBridge()

    audio.start()
    serial_out.start()

    last_mood = None
    last_track_id = None

    try:
        while True:
            amp = audio.get_amplitude()
            mood, track = agent.choose_next_track(amp)

            serial_out.update_state(mood, amp)

            if mood != last_mood:
                print(f"[MOOD] {mood} | amp={amp:.3f}")
                last_mood = mood

            if track and track["id"] != last_track_id:
                filepath = jamendo.download_track(track)
                mixxx.queue_track(filepath)
                cache.mark_played(track)

                print(f"[TRACK] {track['name']} - {track['artist']}")
                last_track_id = track["id"]

            time.sleep(5)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        audio.stop()
        serial_out.stop()


if __name__ == "__main__":
    main()