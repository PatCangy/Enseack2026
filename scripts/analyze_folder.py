"""
PURPOSE:
Analyze all songs in the audio folder and store results.

INPUT:
- audio/ directory

OUTPUT:
- JSON file with features for all songs

TODO:
- [ ] Add progress bar
- [ ] Skip already analyzed files
- [ ] Handle large batches efficiently
- [ ] Add parallel processing
- [ ] Allow genre tagging per file

NOTES:
- Used to build dataset for transitions
- Key step before recommendation engine
"""