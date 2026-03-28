# prototype_app.py
# ─────────────────────────────────────────────────────────────────────────────
# DJ Pipeline — works in two modes:
#
#   HARDWARE_MODE = False  →  PC only, no serial needed.
#                             LED commands are printed in color in the terminal.
#
#   HARDWARE_MODE = True   →  Connects to STM32 Nucleo L476RG via USB serial.
#                             Sends real lighting commands through hardware.py.
#                             Run hardware.py standalone first to verify wiring.
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import time
import threading

from jamendo_client    import JamendoClient
from track_cache       import TrackCache
from dj_agent          import DJAgent
from feature_extractor import FeatureExtractor
from song_classifier   import SongClassifier
from audio_player      import AudioPlayer
from playlist_manager  import save_playlist
from config            import CACHE_DIR, MOOD_TAGS, MOOD_RGB, MOOD_SIDE, RED_CHANNEL_SCALE

# ── Settings ──────────────────────────────────────────────────────────────────
HARDWARE_MODE = False   # ← True when Nucleo is plugged in, False for PC-only test
DEMO_MODE     = True    # ← True = 30s clips,  False = full tracks
N_TRACKS      = 3
SEGMENT_MS    = 30_000  # 30 s per track
CROSSFADE_MS  = 4_000   # 4 s crossfade
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
    msg      = f"{mood},{r_scaled},{g},{b},{side}"
    color    = TERM_COLORS.get(mood, "")
    print(f"  {color}[LED SIM] {mood:10}{RESET}  serial → \"{msg}\"")
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


# ── Hardware LED timeline (Nucleo mode) ───────────────────────────────────────

def hardware_led_timeline(tracks, segment_ms, crossfade_ms, stop_event, nucleo):
    """
    Fires real serial commands to the Nucleo at the right moment for each track.
    Sends a BEAT flash at each transition then holds the mood color.
    """
    offset_s = 0.0
    for i, track in enumerate(tracks):
        if stop_event.is_set():
            break
        time.sleep(offset_s)
        nucleo.on_track_change(
            mood       = track.get("mood", "CALM"),
            track_name = track.get("name", ""),
            artist     = track.get("artist", ""),
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    jamendo   = JamendoClient()
    cache     = TrackCache()
    agent     = DJAgent(jamendo, cache)
    extractor = FeatureExtractor()
    classifier= SongClassifier()
    player    = AudioPlayer()

    # Start Nucleo controller only when hardware is present
    nucleo = None
    if HARDWARE_MODE:
        from hardware import NucleoController
        nucleo = NucleoController(auto_detect=True)
        nucleo.start()
    else:
        print("  [mode] PC-only — LED output simulated in terminal\n")

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
        if nucleo:
            nucleo.stop()
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
            enriched.append(track)
        else:
            try:
                os.remove(track["local_path"])
            except OSError:
                pass

    print(f"\n  [enrich] {len(enriched)} track(s) analyzed\n")

    if not enriched:
        print("No tracks could be analyzed.")
        if nucleo:
            nucleo.stop()
        return

    # ── 3. Gate + score + select ──────────────────────────────────────────────
    selected = agent.choose_tracks_from_enriched(enriched, mood, limit=N_TRACKS)

    if not selected:
        print("No tracks passed the DJ gate. Try a different energy level.")
        if nucleo:
            nucleo.stop()
        return

    for track in selected:
        track["mood"] = classifier.classify_song({
            "tempo": track.get("bpm", 0),
            "rms":   track.get("rms", 0),
        })

    for track in selected:
        cache.mark_played(track)

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
        } for t in selected], f, indent=2)

    # ── 5. Print tracklist ────────────────────────────────────────────────────
    print("\n── Selected tracklist ──────────────────────────────────────────")
    for i, t in enumerate(selected, 1):
        print(
            f"  {i}. {t['name'][:40]}"
            f"  | {t['artist']}"
            f"  | bpm={round(t.get('bpm',0),1)}"
            f"  | mood={t.get('mood')}"
        )
    print("────────────────────────────────────────────────────────────────\n")

    # Print what serial commands will be sent (useful in both modes)
    print("── LED commands ────────────────────────────────────────────────")
    for t in selected:
        r, g, b  = MOOD_RGB[t["mood"]]
        r_scaled = int(r * RED_CHANNEL_SCALE)
        side     = MOOD_SIDE[t["mood"]]
        color    = TERM_COLORS.get(t["mood"], "")
        print(f"  {color}{t['mood']:10}{RESET} → \"{t['mood']},{r_scaled},{g},{b},{side}\"")
    print("────────────────────────────────────────────────────────────────\n")

    # ── 6. Play + LED sync ────────────────────────────────────────────────────
    stop_event = threading.Event()

    if DEMO_MODE:
        print(f"[DEMO] {N_TRACKS} tracks × {SEGMENT_MS//1000}s | {CROSSFADE_MS//1000}s crossfade\n")

        # Choose LED timeline function based on mode
        if HARDWARE_MODE and nucleo:
            led_target = hardware_led_timeline
            led_args   = (selected, SEGMENT_MS, CROSSFADE_MS, stop_event, nucleo)
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

        if HARDWARE_MODE and nucleo:
            # In full mode fire LED change for first track immediately,
            # then rely on the Nucleo's steady-state loop for the rest
            if selected:
                nucleo.on_track_change(
                    mood       = selected[0].get("mood", "CALM"),
                    track_name = selected[0].get("name", ""),
                    artist     = selected[0].get("artist", ""),
                )

        player.play_queue([t["local_path"] for t in selected], crossfade_ms=5000)

    if nucleo:
        nucleo.stop()


if __name__ == "__main__":
    main()