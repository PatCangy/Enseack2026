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
#
# At startup the user is asked:
#   [a] Fixed demo  — always plays the same 3 pre-chosen tracks with exact
#                     timestamps, no downloads required (files must already
#                     be in track_cache/).
#   [b] Standard    — full AI pipeline: fetch → analyze → select → play.
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
N_TRACKS      = 3
SEGMENT_MS    = 30_000  # 30 s per track (standard mode)
CROSSFADE_MS  = 4_000   # 4 s crossfade
# ─────────────────────────────────────────────────────────────────────────────


# ── Fixed demo tracklist ──────────────────────────────────────────────────────

FIXED_DEMO_TRACKS = [
    {
        "id":        "1129271",
        "name":      "Energy",
        "artist":    "Pokki DJ",
        "mood":      "HYPE",
        "genre_tags": ["dance", "electronic"],
        "start_ms":  15_000,
        "end_ms":    46_000,
    },
    {
        "id":        "1179546",
        "name":      "Born Free",
        "artist":    "Pokki DJ",
        "mood":      "ENERGETIC",
        "genre_tags": ["dance", "electronic", "disco"],
        "start_ms":  14_000,
        "end_ms":    45_000,
    },
    {
        "id":        "169151",
        "name":      "Dance Baby",
        "artist":    "Eliot Ness",
        "mood":      "ENERGETIC",
        "genre_tags": ["dance", "electronic"],
        "start_ms":  24_000,
        "end_ms":    46_000,
    },
]

FIXED_DEMO_CROSSFADE_MS = 2_000


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


# ── Fixed demo mode ───────────────────────────────────────────────────────────

def run_fixed_demo(nucleo, jamendo):
    """
    Plays the three pre-chosen tracks using exact start/end timestamps.
    Downloads any missing files first, then slices and crossfades.
    Does NOT touch track_history.json.
    """
    from pydub import AudioSegment
    from pydub.playback import play

    print("\n── Fixed Demo ──────────────────────────────────────────────────")
    print("  Energy → Born Free → Dance Baby  (Pokki DJ / Eliot Ness)")
    print("────────────────────────────────────────────────────────────────\n")

    # ── 1. Ensure all files are downloaded ───────────────────────────────────
    os.makedirs(CACHE_DIR, exist_ok=True)

    for track in FIXED_DEMO_TRACKS:
        filepath = os.path.join(CACHE_DIR, f"{track['id']}.mp3")
        if os.path.exists(filepath):
            print(f"  [cache] Found: {track['name']}")
            track["local_path"] = os.path.abspath(filepath)
        else:
            print(f"  [download] Fetching: {track['name']} — {track['artist']}...")
            # Build a minimal track dict that JamendoClient.download_track expects
            dl_track = {
                "id":        track["id"],
                "name":      track["name"],
                "audio_url": f"https://mp3d.jamendo.com/download/track/{track['id']}/mp31",
            }
            result = jamendo.download_track(dl_track)
            if not result:
                print(f"  [error] Could not download {track['name']}. Aborting demo.")
                return
            track["local_path"] = os.path.abspath(result)
            print(f"  [download] ✓ {track['name']}")

    print()

    # ── 2. Slice exact clip windows ───────────────────────────────────────────
    segments = []
    for track in FIXED_DEMO_TRACKS:
        try:
            audio     = AudioSegment.from_file(track["local_path"])
            start_ms  = track["start_ms"]
            end_ms    = track["end_ms"] if track["end_ms"] is not None else len(audio)

            # Safety clamp
            end_ms = min(end_ms, len(audio))

            clip = audio[start_ms:end_ms]
            segments.append({"clip": clip, "track": track})

            duration_s = len(clip) / 1000
            print(f"  ✓  {track['name'][:35]} — {track['artist']}"
                  f"  ({start_ms//1000}s → {end_ms//1000}s, {duration_s:.1f}s clip)"
                  f"  mood={track['mood']}")

        except Exception as e:
            print(f"  [error] Could not slice {track['name']}: {e}")
            return

    print()

    # ── 3. Stitch with crossfade ──────────────────────────────────────────────
    mix = segments[0]["clip"]
    for seg in segments[1:]:
        mix = mix.append(seg["clip"], crossfade=FIXED_DEMO_CROSSFADE_MS)

    total_s = len(mix) / 1000
    print(f"  [demo] Mix ready — {total_s:.1f}s total")

    # ── 4. Print LED commands ─────────────────────────────────────────────────
    print("\n── LED commands ────────────────────────────────────────────────")
    for seg in segments:
        t        = seg["track"]
        r, g, b  = MOOD_RGB[t["mood"]]
        r_scaled = int(r * RED_CHANNEL_SCALE)
        side     = MOOD_SIDE[t["mood"]]
        color    = TERM_COLORS.get(t["mood"], "")
        print(f"  {color}{t['mood']:10}{RESET} → \"{t['mood']},{r_scaled},{g},{b},{side}\"")
    print("────────────────────────────────────────────────────────────────\n")

    # ── 5. Play + LED sync ────────────────────────────────────────────────────
    stop_event    = threading.Event()
    playback_done = threading.Event()

    def _play():
        play(mix)
        playback_done.set()
        stop_event.set()

    play_thread = threading.Thread(target=_play, daemon=True)
    play_thread.start()

    # LED timeline — fire at the start of each clip accounting for crossfade
    def _led_timeline():
        clip_durations = [len(s["clip"]) for s in segments]
        offset_s = 0.0
        for i, seg in enumerate(segments):
            if stop_event.is_set():
                break
            time.sleep(offset_s)
            t = seg["track"]
            if HARDWARE_MODE and nucleo:
                nucleo.on_track_change(
                    mood       = t["mood"],
                    track_name = t["name"],
                    artist     = t["artist"],
                )
            else:
                simulate_led(t["mood"], t["name"], t["artist"])

            if i < len(segments) - 1:
                # Next LED fires after this clip minus the crossfade overlap
                offset_s = (clip_durations[i] - FIXED_DEMO_CROSSFADE_MS) / 1000

    led_thread = threading.Thread(target=_led_timeline, daemon=True)
    led_thread.start()

    print("  [demo] Starting playback...\n")
    playback_done.wait()
    led_thread.join(timeout=1)
    print("\n  [demo] Playback complete.")


# ── Standard mode (full AI pipeline) ─────────────────────────────────────────

def run_standard(nucleo, jamendo, cache, agent, extractor, classifier, player,
                 room_energy):
    clear_cache_folder()

    # ── 1. Mood + fetch ───────────────────────────────────────────────────────
    mood = agent.classify_mood(room_energy)
    tags = MOOD_TAGS[mood]
    print(f"Target mood: {mood}  |  tags: {tags}\n")

    candidates = jamendo.search_tracks(tags, limit=max(20, N_TRACKS * 6))
    candidates = cache.filter_unplayed(candidates, recent_limit=5)
    print(f"  [fetch] {len(candidates)} candidate(s) after removing recently played\n")

    if not candidates:
        print("No new candidates. Delete track_history.json to reset.")
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
        return

    # ── 3. Gate + score + select ──────────────────────────────────────────────
    selected = agent.choose_tracks_from_enriched(enriched, mood, limit=N_TRACKS)

    if not selected:
        print("No tracks passed the DJ gate. Try a different energy level.")
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    jamendo    = JamendoClient()
    cache      = TrackCache()
    agent      = DJAgent(jamendo, cache)
    extractor  = FeatureExtractor()
    classifier = SongClassifier()
    player     = AudioPlayer()

    nucleo = None
    if HARDWARE_MODE:
        from hardware import NucleoController
        nucleo = NucleoController(auto_detect=True)
        nucleo.start()
    else:
        print("  [mode] PC-only — LED output simulated in terminal\n")

    # ── Room energy ───────────────────────────────────────────────────────────
    try:
        room_energy = int(input("Room energy (1-10): "))
        room_energy = max(1, min(10, room_energy))
    except ValueError:
        print("Invalid input. Defaulting to 5.")
        room_energy = 5

    # ── Mode selection ────────────────────────────────────────────────────────
    print()
    mode = input("Run mode — [a] fixed demo  [b] standard: ").strip().lower()
    print()

    if mode == "a":
        run_fixed_demo(nucleo, jamendo)
    else:
        run_standard(nucleo, jamendo, cache, agent, extractor, classifier,
                     player, room_energy)

    if nucleo:
        nucleo.stop()


if __name__ == "__main__":
    main()