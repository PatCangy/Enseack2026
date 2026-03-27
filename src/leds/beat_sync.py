"""
PURPOSE:
Sync LED signals (or simulated output) with beat timestamps.

INPUT:
- beat_timestamps: list of times (seconds) where beats occur

OUTPUT:
- triggers (print statements for now, later hardware signals)

TODO:
- [ ] Replace print statements with real hardware output (Arduino/ESP32)
- [ ] Add non-blocking timing (avoid busy-wait loop)
- [ ] Support variable BPM changes
- [ ] Sync with actual audio playback (important!)
- [ ] Add intensity control (stronger beats vs weak beats)

NOTES:
- This is the bridge between audio analysis and physical LEDs
- Will later send signals via serial/WebSocket
"""