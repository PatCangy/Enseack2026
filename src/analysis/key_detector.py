"""
PURPOSE:
Estimate the musical key of a song using chroma features.

INPUT:
- y: audio time series
- sr: sample rate

OUTPUT:
- key: estimated pitch class (e.g., C, D#, A)

TODO:
- [ ] Improve accuracy (detect major vs minor)
- [ ] Implement harmonic key detection (Camelot wheel)
- [ ] Smooth chroma features over time
- [ ] Add confidence score for key estimation
- [ ] Evaluate performance across genres

NOTES:
- Current implementation is basic (dominant pitch class)
- More advanced harmonic analysis can improve transition quality
"""