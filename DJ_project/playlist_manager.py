# playlist_manager.py

import os


def save_playlist(tracks, cache_dir, filename="generated_playlist.m3u"):
    os.makedirs(cache_dir, exist_ok=True)
    filepath = os.path.join(cache_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for track in tracks:
            local_path = track.get("local_path")
            if local_path:
                # Write extended info line then path — helps media players show metadata
                duration = track.get("duration", -1)
                name     = track.get("name", "Unknown")
                artist   = track.get("artist", "Unknown")
                f.write(f"#EXTINF:{duration},{artist} - {name}\n")
                f.write(local_path + "\n")

    return filepath