"""
PURPOSE:
Perform a basic crossfade transition between two audio tracks.

INPUT:
- path_a: first song file
- path_b: second song file
- output_path: where to save mixed result
- crossfade_ms: duration of crossfade in milliseconds

OUTPUT:
- saved mixed audio file

TODO:
- [ ] Align beats before crossfading (important!)
- [ ] Implement BPM matching (time-stretching)
- [ ] Add fade curves (linear vs exponential)
- [ ] Add EQ/filter effects (DJ-style transitions)
- [ ] Support different transition styles (smooth, drop, etc.)

NOTES:
- Current version is simple (no beat matching)
- Will be upgraded to "smart transition engine"
"""