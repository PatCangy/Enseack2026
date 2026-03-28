# prototype_app.py
# ─────────────────────────────────────────────────────────────────────────────
# DJ Pipeline — works in two modes:
#
#   HARDWARE_MODE = False  →  PC only, no serial needed.
#                             LED commands are printed in color in the terminal.
#
#   HARDWARE_MODE = True   →  Connects to Arduino Mega 2560 via USB serial.
#                             Sends real lighting commands through hardware.py.
#                             Run hardware.py standalone first to verify wiring.
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import time
import threading

from pydub import AudioSegment
from pydub.playback import play

from jamendo_client import JamendoClient
from track_cache import TrackCache
from dj_agent import DJAgent
from feature_extractor import FeatureExtractor
from song_classifier import SongClassifier
from audio_player import AudioPlayer
from playlist_manager import save_playlist
from beat_detector import BeatDetector
from config import CACHE_DIR, MOOD_TAGS, MOOD_RGB, MOOD_SIDE, RED_CHANNEL_SCALE

# ── Settings ──────────────────────────────────────────────────────────────────
HARDWARE_MODE    = True  # True when Arduino is plugged in
BLACKHOLE_DEVICE = 0      # sounddevice index for BlackHole 2ch
DEMO_MODE = True        # True = 30s clips, False = full tracks
N_TRACKS = 3
SEGMENT_MS = 30_000
CROSSFADE_MS = 4_000

# Terminal testing
TERMINAL_TEST_MODE = True
PREVIEW_MS = 12_000         # 12-second preview per track
PREVIEW_START_RATIO = 0.20  # start 20% into the song to skip intros
# ─────────────────────────────────────────────────────────────────────────────


# ── Terminal LED simulation (PC mode) ─────────────────────────────────────────
TERM_COLORS = {
    "CALM":      "\033[94m",
    "WARM":      "\033[93m",
    "ENERGETIC": "\033[95m",
    "HYPE":      "\033[91m",
}
RESET = "\033[0m"


def simulate_led(mood, track_name, artist):
    r, g, b  = MOOD_RGB[mood]
    r_scaled = int(r * RED_CHANNEL_SCALE)
    side     = MOOD_SIDE[mood]
    msg      = f"MOOD,{r_scaled},{g},{b},{side}"
    color    = TERM_COLORS.get(mood, "")
    print(f'  {color}[LED SIM] {mood:10}{RESET}  serial → "{msg}"')
    print(f"            🎵  {track_name[:45]} — {artist}")


def simulate_led_timeline(tracks, segment_ms, crossfade_ms, stop_event):
    offset_s = 0.0
    for i, track in enumerate(tracks):
        if stop_event.is_set():
            break
        time.sleep(offset_s)
        simulate_led(
            track.get("mood", "CALM"),
            track.get("name", "Unknown"),
            track.get("artist", ""),
        )
        if i < len(tracks) - 1:
            offset_s = (segment_ms - crossfade_ms) / 1000


# ── Hardware LED timeline (Arduino mode) ──────────────────────────────────────
def hardware_led_timeline(tracks, segment_ms, crossfade_ms, stop_event, arduino):
    offset_s = 0.0
    for i, track in enumerate(tracks):
        if stop_event.is_set():
            break
        time.sleep(offset_s)
        arduino.on_track_change(
            mood=track.get("mood", "CALM"),
            track_name=track.get("name", ""),
            artist=track.get("artist", ""),
        )
        if i < len(tracks) - 1:
            offset_s = (segment_ms - crossfade_ms) / 1000


# ── Helpers ───────────────────────────────────────────────────────────────────
def clear_cache_folder():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        return

    removed = 0
    for filename in os.listdir(CACHE_DIR):
        if filename.endswith(".mp3") or filename.endswith(".m3u"):
            try:
                os.remove(os.path.join(CACHE_DIR, filename))
                removed += 1
            except OSError:
                pass

    if removed:
        print(f"  [cache] Cleared {removed} file(s) from {CACHE_DIR}/")


def preview_track(track, preview_ms=PREVIEW_MS, start_ratio=PREVIEW_START_RATIO):
    path = track.get("local_path")
    if not path or not os.path.exists(path):
        print("  [preview] File not found.")
        return

    name       = track.get("name", "Unknown")
    artist     = track.get("artist", "Unknown")
    bpm        = round(float(track.get("bpm", 0)), 1) if track.get("bpm") is not None else "?"
    rms        = round(float(track.get("rms", 0)), 4) if track.get("rms") is not None else "?"
    target_mood = track.get("mood", "UNKNOWN")
    audio_mood  = track.get("audio_mood", "UNKNOWN")

    try:
        audio    = AudioSegment.from_file(path)
        start_ms = int(len(audio) * start_ratio)
        end_ms   = start_ms + preview_ms

        if end_ms > len(audio):
            start_ms = max(0, len(audio) - preview_ms)
            end_ms   = len(audio)

        clip = audio[start_ms:end_ms]

        print("\n── Preview ─────────────────────────────────────────────────────")
        print(f"  {name} — {artist}")
        print(f"  bpm={bpm} | rms={rms} | target={target_mood} | audio={audio_mood}")
        print(f"  preview: {len(clip)/1000:.1f}s")
        print("────────────────────────────────────────────────────────────────")
        play(clip)
        print("  [preview] done\n")

    except Exception as e:
        print(f"  [preview] Could not play track: {e}")


def build_ranked_debug_list(agent, tracks, mood):
    ranked = []
    for track in tracks:
        try:
            score = agent.mood_fit_score(track, mood)
        except Exception:
            score = 0
        ranked.append((score, track))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked


def print_debug_track_table(ranked_tracks, selected, mood):
    selected_paths = {t.get("local_path") for t in selected}

    print("\n── Candidate tracks ranked for target mood ─────────────────────")
    print(f"  Target mood: {mood}\n")

    for i, (score, track) in enumerate(ranked_tracks, 1):
        chosen     = "✓" if track.get("local_path") in selected_paths else " "
        bpm        = round(float(track.get("bpm", 0)), 1) if track.get("bpm") is not None else "?"
        rms        = round(float(track.get("rms", 0)), 4) if track.get("rms") is not None else "?"
        audio_mood = track.get("audio_mood", "UNKNOWN")
        genres     = ", ".join(track.get("genre_tags", [])[:3]) if track.get("genre_tags") else "-"

        print(
            f"  [{i:02}] {chosen} "
            f"{track.get('name', 'Unknown')[:32]:32} | "
            f"{track.get('artist', 'Unknown')[:18]:18} | "
            f"score={score:>5} | bpm={bpm:>5} | rms={rms:>6} | "
            f"audio={audio_mood:10} | genres={genres}"
        )

    print("────────────────────────────────────────────────────────────────")
    print("  ✓ = chosen by the agent")
    print("  Type a track number to preview it")
    print("  Type 's' to preview the selected tracks in order")
    print("  Type 'c' to continue to the final demo/playback")
    print("  Type 'q' to quit")
    print("────────────────────────────────────────────────────────────────\n")


def terminal_test_menu(agent, mood, enriched, selected):
    ranked_tracks = build_ranked_debug_list(agent, enriched, mood)

    while True:
        print_debug_track_table(ranked_tracks, selected, mood)
        command = input("Command: ").strip().lower()

        if command == "c":
            return True

        if command == "q":
            return False

        if command == "s":
            print("\n  [test] Previewing selected tracks in order...\n")
            for track in selected:
                preview_track(track)
            continue

        if command.isdigit():
            index = int(command) - 1
            if 0 <= index < len(ranked_tracks):
                _, track = ranked_tracks[index]
                preview_track(track)
            else:
                print("  [test] Invalid track number.\n")
            continue

        print("  [test] Unknown command.\n")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    jamendo    = JamendoClient()
    cache      = TrackCache()
    agent      = DJAgent(jamendo, cache)
    extractor  = FeatureExtractor()
    classifier = SongClassifier()
    player     = AudioPlayer()

    arduino = None
    if HARDWARE_MODE:
        from hardware import ArduinoController
        arduino = ArduinoController(auto_detect=True)
        arduino.start()
    else:
        print("  [mode] PC-only — LED output simulated in terminal\n")

    # ── Beat detector (loopback via BlackHole) ────────────────────────────────
    # Fires a BEAT serial message in sync with the music's actual rhythm.
    # Only active in HARDWARE_MODE — in PC mode beats are printed to terminal.
    beat_detector = None
    if HARDWARE_MODE and arduino:
        def on_beat():
            mood = arduino._mood  # get current mood from the controller
            arduino._send(arduino._beat_message(mood))

        beat_detector = BeatDetector(on_beat=on_beat, device=BLACKHOLE_DEVICE)

    try:
        room_energy = int(input("Room energy (1-10): "))
        room_energy = max(1, min(10, room_energy))
    except ValueError:
        print("Invalid input. Defaulting to 5.")
        room_energy = 5

    print()
    clear_cache_folder()

    # ── 1. Mood + fetch ───────────────────────────────────────────────────────
    mood = agent.classify_mood(room_energy)
    tags = MOOD_TAGS[mood]
    print(f"Target mood: {mood}  |  tags: {tags}\n")

    candidates = jamendo.search_tracks(tags, limit=max(20, N_TRACKS * 6))
    candidates = cache.filter_unplayed(candidates)
    print(f"  [fetch] {len(candidates)} candidate(s) after removing recently played\n")

    if not candidates:
        print("No new candidates. Delete track_history.json to reset.")
        if arduino:
            arduino.stop()
        return

    # ── 2. Download + enrich with librosa ─────────────────────────────────────
    print("Downloading candidates for BPM analysis...")
    enriched = []

    for track in candidates:
        print(f"  Downloading: {track['name']} — {track['artist']}")
        filepath = jamendo.download_track(track)
        if not filepath:
            print("    [skip] Download failed")
            continue

        track["local_path"] = os.path.abspath(filepath)

        if extractor.enrich_track(track, track["local_path"]):
            track["genre_tags"] = agent.extract_genre_tags(track)
            track["audio_mood"] = classifier.classify_song({
                "tempo": track.get("bpm", 0),
                "rms":   track.get("rms", 0),
            })
            enriched.append(track)
        else:
            try:
                os.remove(track["local_path"])
            except OSError:
                pass

    print(f"\n  [enrich] {len(enriched)} track(s) analyzed\n")

    if not enriched:
        print("No tracks could be analyzed.")
        if arduino:
            arduino.stop()
        return

    # ── 3. Gate + score + select ──────────────────────────────────────────────
    selected = agent.choose_tracks_from_enriched(enriched, mood, limit=N_TRACKS)

    if not selected:
        print("No tracks passed the DJ gate. Try a different energy level.")
        if arduino:
            arduino.stop()
        return

    for track in selected:
        track["audio_mood"] = classifier.classify_song({
            "tempo": track.get("bpm", 0),
            "rms":   track.get("rms", 0),
        })
        track["mood"] = mood

    # ── 3.5 Terminal test mode ────────────────────────────────────────────────
    if TERMINAL_TEST_MODE:
        should_continue = terminal_test_menu(agent, mood, enriched, selected)
        if not should_continue:
            print("  [test] Stopped before final playback.")
            if arduino:
                arduino.stop()
            return

    # Mark only after confirming the chosen tracks
    for track in selected:
        cache.mark_played(track)

    # Remove unselected audio files after testing is done
    selected_paths = {t["local_path"] for t in selected}
    for track in enriched:
        p = track.get("local_path")
        if p and p not in selected_paths:
            try:
                os.remove(p)
            except OSError:
                pass

    # ── 4. Save playlist + features ───────────────────────────────────────────
    save_playlist(selected, CACHE_DIR)

    with open("song_features.json", "w", encoding="utf-8") as f:
        json.dump([{
            "path":      t["local_path"],
            "tempo":     t.get("bpm", 0),
            "rms":       t.get("rms", 0),
            "centroid":  t.get("centroid", 0),
            "bandwidth": t.get("bandwidth", 0),
            "mood":      t.get("mood"),
            "audio_mood": t.get("audio_mood"),
            "genre_tags": t.get("genre_tags", []),
        } for t in selected], f, indent=2)

    # ── 5. Print tracklist ────────────────────────────────────────────────────
    print("\n── Selected tracklist ──────────────────────────────────────────")
    for i, t in enumerate(selected, 1):
        print(
            f"  {i}. {t['name'][:40]}"
            f"  | {t['artist']}"
            f"  | bpm={round(t.get('bpm', 0), 1)}"
            f"  | target={t.get('mood')}"
            f"  | audio={t.get('audio_mood')}"
        )
    print("────────────────────────────────────────────────────────────────\n")

    # Print serial commands exactly as they will be sent
    print("── LED commands ────────────────────────────────────────────────")
    for t in selected:
        r, g, b  = MOOD_RGB[t["mood"]]
        r_scaled = int(r * RED_CHANNEL_SCALE)
        side     = MOOD_SIDE[t["mood"]]
        color    = TERM_COLORS.get(t["mood"], "")
        # First message on track change is always BEAT (triggers wave + sets color)
        beat_msg = f"BEAT,{r_scaled},{g},{b},{side}"
        mood_msg = f"MOOD,{r_scaled},{g},{b},{side}"
        print(f'  {color}{t["mood"]:10}{RESET} → beat: "{beat_msg}"  then: "{mood_msg}"')
    print("────────────────────────────────────────────────────────────────\n")

    # ── 6. Play + LED sync ────────────────────────────────────────────────────
    stop_event = threading.Event()

    # Start beat detector now — audio capture begins with playback
    if beat_detector:
        beat_detector.start()

    if DEMO_MODE:
        print(f"[DEMO] {len(selected)} tracks × {SEGMENT_MS//1000}s | {CROSSFADE_MS//1000}s crossfade\n")

        if HARDWARE_MODE and arduino:
            led_target = hardware_led_timeline
            led_args   = (selected, SEGMENT_MS, CROSSFADE_MS, stop_event, arduino)
        else:
            led_target = simulate_led_timeline
            led_args   = (selected, SEGMENT_MS, CROSSFADE_MS, stop_event)

        led_thread = threading.Thread(target=led_target, args=led_args, daemon=True)
        led_thread.start()

        player.play_demo(selected, segment_ms=SEGMENT_MS, crossfade_ms=CROSSFADE_MS)

        stop_event.set()
        led_thread.join(timeout=1)

    else:
        print("[FULL MODE] Playing complete tracks...\n")

        if HARDWARE_MODE and arduino and selected:
            arduino.on_track_change(
                mood=selected[0].get("mood", "CALM"),
                track_name=selected[0].get("name", ""),
                artist=selected[0].get("artist", ""),
            )

        player.play_queue([t["local_path"] for t in selected], crossfade_ms=5000)

    if beat_detector:
        beat_detector.stop()

    if arduino:
        arduino.stop()


if __name__ == "__main__":
    main()