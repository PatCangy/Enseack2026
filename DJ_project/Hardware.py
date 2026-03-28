# hardware.py
# ─────────────────────────────────────────────────────────────────────────────
# Arduino Mega 2560 — Serial Communication Layer
#
# This file is the bridge between the Python DJ software and the Arduino Mega.
# It runs alongside prototype_app.py and sends lighting commands to the Mega
# over USB serial.
#
# ── Serial message format sent to Arduino ────────────────────────────────────
#   "MOOD,R,G,B,SIDE\n"   — update wave color for next beat
#   "BEAT,R,G,B,SIDE\n"   — update color AND fire a wave immediately
#
#   Field   Type    Range       Description
#   ──────  ──────  ──────────  ─────────────────────────────────────────────
#   MOOD    str     MOOD/BEAT   Message type prefix
#   R       int     0–255       Red channel (already scaled by RED_CHANNEL_SCALE)
#   G       int     0–255       Green channel
#   B       int     0–255       Blue channel
#   SIDE    int     0b0001–     Bitmask: which sides of the LED matrix are active
#                   0b1111      (received by Arduino but not used in this sketch)
#
#   Examples:
#     MOOD,0,0,255,1        → blue wave color set
#     BEAT,255,255,255,15   → white wave triggered immediately
#     MOOD,161,120,0,3      → orange wave color set
#
# ── Wiring ────────────────────────────────────────────────────────────────────
#   Connect Arduino Mega to PC via USB-A to USB-B cable.
#   On Mac/Linux it appears as /dev/tty.usbmodem* or /dev/ttyACM0
#   On Windows it appears as COM3, COM4, etc.
#   Set SERIAL_PORT in config.py to match your system, or let auto-detect
#   find it automatically.
# ─────────────────────────────────────────────────────────────────────────────

import threading
import time
import serial
import serial.tools.list_ports

from config import (
    SERIAL_PORT,
    SERIAL_BAUDRATE,
    SERIAL_INTERVAL,
    MOOD_RGB,
    MOOD_SIDE,
    RED_CHANNEL_SCALE,
)


# ── Auto-detect Arduino port ──────────────────────────────────────────────────

def find_arduino_port():
    """
    Tries to auto-detect the Arduino Mega's COM port by scanning connected
    USB serial devices. Checks for Arduino, Mega, CH340 (clone boards),
    FTDI, and STM identifiers.
    Falls back to SERIAL_PORT from config.py if none found.
    """
    KNOWN_KEYWORDS = ["arduino", "mega", "ch340", "ftdi", "stm", "nucleo", "stlink"]

    for port in serial.tools.list_ports.comports():
        desc = (port.description or "").lower()
        mfr  = (port.manufacturer or "").lower()
        if any(kw in desc or kw in mfr for kw in KNOWN_KEYWORDS):
            print(f"  [hardware] Auto-detected Arduino on {port.device}  ({port.description})")
            return port.device

    print(f"  [hardware] Arduino not auto-detected. Using config port: {SERIAL_PORT}")
    print(f"  [hardware] Available ports:")
    for port in serial.tools.list_ports.comports():
        print(f"             {port.device}  —  {port.description}")
    return SERIAL_PORT


# ── ArduinoController ─────────────────────────────────────────────────────────

class ArduinoController:
    """
    Manages the serial connection to the Arduino Mega 2560 and sends
    real-time lighting commands based on the current DJ mood.

    Usage:
        arduino = ArduinoController()
        arduino.start()

        # When a new track starts:
        arduino.on_track_change(mood="ENERGETIC", track_name="All Night")

        # On mood update only (no wave trigger):
        arduino.update_mood("ENERGETIC")

        # On shutdown:
        arduino.stop()
    """

    def __init__(self, auto_detect=True):
        port         = find_arduino_port() if auto_detect else SERIAL_PORT
        self.port    = port
        self.baud    = SERIAL_BAUDRATE
        self.ser     = None
        self.running = False
        self.thread  = None

        self._lock        = threading.Lock()
        self._mood        = "CALM"
        self._connected   = False
        self._warned_once = False

        self._reader_thread = None

    # ── Connection ────────────────────────────────────────────────────────────

    def _connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            # Give the Arduino 2s to finish its bootloader reset after connection
            time.sleep(2.0)
            self._connected   = True
            self._warned_once = False
            print(f"  [hardware] Connected to Arduino on {self.port} @ {self.baud} baud")
        except serial.SerialException as e:
            self.ser        = None
            self._connected = False
            if not self._warned_once:
                print(f"  [hardware] Cannot open {self.port}: {e}")
                print(f"  [hardware] Check SERIAL_PORT in config.py and that the Arduino is plugged in.")
                self._warned_once = True

    def _disconnect(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.ser        = None
        self._connected = False

    # ── Message builders ──────────────────────────────────────────────────────

    def _mood_message(self, mood):
        """
        Builds a color-update message (no immediate wave trigger):
        "MOOD,R,G,B,SIDE\n"
        """
        r, g, b = MOOD_RGB[mood]
        r       = int(r * RED_CHANNEL_SCALE)
        side    = MOOD_SIDE[mood]
        return f"MOOD,{r},{g},{b},{side}\n"

    def _beat_message(self, mood):
        """
        Builds a beat message that sets the mood color AND triggers a wave:
        "BEAT,R,G,B,SIDE\n"
        Uses the actual mood color (not hardcoded white) so the wave matches
        the incoming track's mood.
        """
        r, g, b = MOOD_RGB[mood]
        r       = int(r * RED_CHANNEL_SCALE)
        side    = MOOD_SIDE[mood]
        return f"BEAT,{r},{g},{b},{side}\n"

    # ── Serial write ──────────────────────────────────────────────────────────

    def _send(self, message):
        """Thread-safe serial write. Reconnects if the connection dropped."""
        with self._lock:
            if self.ser is None or not self.ser.is_open:
                self._connect()

            if self.ser and self.ser.is_open:
                try:
                    self.ser.write(message.encode("utf-8"))
                    return True
                except serial.SerialException as e:
                    print(f"  [hardware] Write error: {e}. Reconnecting...")
                    self._disconnect()
        return False

    # ── Public API ────────────────────────────────────────────────────────────

    def update_mood(self, mood):
        """Update the current mood. The send loop will pick this up within 50ms."""
        with self._lock:
            self._mood = mood

    def on_track_change(self, mood, track_name="", artist=""):
        """
        Call this at the START of each new track.
        Sends a BEAT message (triggers wave + sets mood color in one message),
        then keeps the mood updated for the continuous send loop.
        """
        print(f"  [hardware] Track change → mood={mood}  🎵  {track_name} — {artist}")

        # Single BEAT message: sets color AND fires the wave on the Arduino
        self._send(self._beat_message(mood))

        # Update internal mood so the send loop keeps refreshing it
        self.update_mood(mood)

    # ── Background send loop ──────────────────────────────────────────────────

    def _send_loop(self):
        """
        Runs in a background thread.
        Sends the current mood color every SERIAL_INTERVAL seconds (50ms).
        This resets the Arduino's idle timeout so it never falls back to blue
        while a track is actively playing.
        """
        while self.running:
            with self._lock:
                mood = self._mood
            self._send(self._mood_message(mood))
            time.sleep(SERIAL_INTERVAL)

    # ── Read ACK from Arduino ─────────────────────────────────────────────────

    def _reader_loop(self):
        """
        Reads lines sent back from the Arduino (e.g. "ACK\n").
        Optional — useful during development to confirm delivery.
        """
        while self.running:
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        print(f"  [Arduino] ← {line}")
            except Exception:
                pass
            time.sleep(0.01)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if self.running:
            return
        self.running = True
        self._connect()

        self.thread = threading.Thread(target=self._send_loop, daemon=True)
        self.thread.start()

        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

        print("  [hardware] ArduinoController started")

    def stop(self):
        self.running = False
        time.sleep(0.1)
        self._disconnect()
        print("  [hardware] ArduinoController stopped")


# ── Backwards-compatible alias ────────────────────────────────────────────────
# prototype_app.py imports NucleoController — this keeps it working without
# touching that file.
NucleoController = ArduinoController


# ── Standalone test ───────────────────────────────────────────────────────────
# Run:  python hardware.py
# Cycles through all 4 moods with a beat-triggered wave between each.

if __name__ == "__main__":
    print("═" * 55)
    print("  Arduino Mega Hardware Test — cycles through all moods")
    print("  Press Ctrl+C to stop")
    print("═" * 55 + "\n")

    arduino = ArduinoController(auto_detect=True)
    arduino.start()

    moods = ["CALM", "WARM", "ENERGETIC", "HYPE"]

    try:
        for cycle in range(2):
            for mood in moods:
                print(f"\n  Testing mood: {mood}")
                arduino.on_track_change(mood, track_name=f"Test track ({mood})")
                time.sleep(4)

        print("\n  Test complete.")

    except KeyboardInterrupt:
        print("\n  Interrupted by user.")

    finally:
        arduino.stop()