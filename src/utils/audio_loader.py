"""
PURPOSE:
Load audio files into a format usable by analysis modules.

INPUT:
- file path

OUTPUT:
- y: audio time series
- sr: sample rate

TODO:
- [ ] Handle multiple formats (WAV, MP3, FLAC)
- [ ] Add error handling for invalid files
- [ ] Normalize audio levels
- [ ] Optionally trim silence at beginning/end
- [ ] Support stereo → mono conversion options

NOTES:
- This is the entry point for all audio processing
"""