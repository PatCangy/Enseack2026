"""
PURPOSE:
Extract all relevant audio features from a song and package them into a structured format.

INPUT:
- path: file path to audio file
- genre: optional metadata (default = "unknown")

OUTPUT:
- dictionary containing:
    - file_name
    - bpm
    - beat_timestamps
    - key
    - genre

TODO:
- [ ] Add energy/loudness feature
- [ ] Add spectral features (brightness, etc.)
- [ ] Add duration and section detection (intro/chorus)
- [ ] Normalize output format for all songs
- [ ] Handle errors for unsupported/corrupt files

NOTES:
- This is the main "analysis pipeline"
- Output will be stored in JSON and used by other modules
"""