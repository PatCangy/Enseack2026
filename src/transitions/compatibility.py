"""
PURPOSE:
Compute a compatibility score between two songs based on musical features.

INPUT:
- song_a: dictionary of features (from feature_extractor)
- song_b: dictionary of features

OUTPUT:
- score: numerical value representing how well the songs match

TODO:
- [ ] Improve scoring logic (weight BPM, key, genre differently)
- [ ] Add harmonic compatibility (relative keys, Camelot system)
- [ ] Penalize large tempo differences more intelligently
- [ ] Add energy matching (smooth transitions)
- [ ] Normalize score to a consistent range (e.g., 0–100)

NOTES:
- This is the "decision engine" of the AI DJ
- Used to recommend next song in playlist
"""