# AI DJ Hackathon

A hackathon project that analyzes songs, extracts musical features, recommends transitions, and syncs LEDs to music.

## Core MVP
- Extract BPM
- Extract beat timestamps
- Extract key
- Use genre metadata
- Transition songs with BPM alignment + crossfade
- Sync LEDs to beats

## Project Structure
- `src/analysis/` -> audio analysis
- `src/transitions/` -> song matching and transitions
- `src/leds/` -> LED logic
- `src/playback/` -> playback tools
- `scripts/` -> runnable demos
- `audio/` -> input songs
- `data/` -> extracted song feature JSON
- `output/` -> generated mixed files

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt