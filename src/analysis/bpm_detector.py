"""
PURPOSE:
Detect the tempo (BPM) and beat positions of an audio signal.

INPUT:
- y: audio time series (numpy array)
- sr: sample rate

OUTPUT:
- bpm: estimated tempo of the song
- beat_times: list of timestamps (seconds) where beats occur

TODO:
- [ ] Improve BPM accuracy (handle half-time/double-time errors)
- [ ] Add smoothing or filtering for noisy signals
- [ ] Optionally detect downbeats (start of bars)
- [ ] Add confidence score for BPM detection
- [ ] Optimize for real-time or faster processing

NOTES:
- This is one of the most critical modules for LED sync and transitions
- Beat timestamps will drive LED timing and transition alignment
"""