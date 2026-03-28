# hardware.py
# ─────────────────────────────────────────────────────────────────────────────
# STM32 NUCLEO L476RG — Serial Communication Layer
#
# This file is the bridge between the Python DJ software and the Nucleo board.
# It runs alongside prototype_app.py (or your final app) and sends lighting
# commands to the Nucleo over USB/UART serial.
#
# ── What this file does ───────────────────────────────────────────────────────
#   • Connects to the Nucleo over serial (USB virtual COM port)
#   • Sends a structured message every 50ms with current mood + RGB + side mask
#   • Reacts to track transitions: fires a BEAT FLASH then settles to mood color
#   • Reads ACK responses from the Nucleo (optional, for debugging)
#   • Handles reconnection automatically if the cable is unplugged mid-demo
#
# ── Serial message format sent to Nucleo ─────────────────────────────────────
#   "MOOD,R,G,B,SIDE\n"
#
#   Field   Type    Range       Description
#   ──────  ──────  ──────────  ─────────────────────────────────────────────
#   MOOD    str     CALM etc    Human-readable mood label (for Nucleo debug)
#   R       int     0–255       Red channel (already scaled by RED_CHANNEL_SCALE)
#   G       int     0–255       Green channel
#   B       int     0–255       Blue channel
#   SIDE    int     0b0001–     Bitmask: which sides of the LED matrix are active
#                   0b1111      0001=1 side, 0011=2, 0111=3, 1111=all 4
#
#   Examples:
#     CALM,0,0,255,1        → blue, 1 side lit
#     WARM,161,120,0,3      → orange, 2 sides lit
#     ENERGETIC,161,0,120,7 → pink, 3 sides lit
#     HYPE,161,0,0,15       → red, all 4 sides lit
#
# ── Beat flash message ────────────────────────────────────────────────────────
#   "BEAT,255,255,255,15\n"
#   Sent once at each track transition — full white, all sides, for 200ms,
#   then the Nucleo returns to the mood color automatically.
#
# ── What the Nucleo firmware needs to do ─────────────────────────────────────
#   1. Read serial line until '\n'
#   2. Split by ','  → [mood, r, g, b, side]
#   3. If mood == "BEAT": flash white for 200ms then revert to last mood color
#   4. Otherwise: set LED matrix to (r, g, b) on the sides defined by the mask
#   5. (Optional) send back "ACK\n" so Python can confirm delivery
#
# ── Wiring ────────────────────────────────────────────────────────────────────
#   Connect Nucleo to PC via USB-A to Mini-B cable (the same one used for
#   flashing). The Nucleo exposes a virtual COM port (STLink VCP).
#   On Mac/Linux it appears as /dev/tty.usbmodem* or /dev/ttyACM0
#   On Windows it appears as COM3, COM4, etc.
#   Set SERIAL_PORT in config.py to match your system.
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


# ── Auto-detect Nucleo port ───────────────────────────────────────────────────

def find_nucleo_port():
    """
    Tries to auto-detect the Nucleo's virtual COM port by scanning connected
    USB serial devices for STMicroelectronics identifiers.
    Falls back to SERIAL_PORT from config.py if none found.
    """
    for port in serial.tools.list_ports.comports():
        desc = (port.description or "").lower()
        mfr  = (port.manufacturer or "").lower()
        if "stm" in desc or "nucleo" in desc or "stlink" in desc or "stm" in mfr:
            print(f"  [hardware] Auto-detected Nucleo on {port.device}")
            return port.device

    print(f"  [hardware] Nucleo not auto-detected. Using config port: {SERIAL_PORT}")
    print(f"  [hardware] Available ports:")
    for port in serial.tools.list_ports.comports():
        print(f"             {port.device}  —  {port.description}")
    return SERIAL_PORT


# ── NucleoController ──────────────────────────────────────────────────────────

class NucleoController:
    """
    Manages the serial connection to the STM32 Nucleo L476RG and sends
    real-time lighting commands based on the current DJ mood.

    Usage:
        nucleo = NucleoController()
        nucleo.start()

        # When a new track starts:
        nucleo.on_track_change(mood="ENERGETIC", track_name="All Night")

        # Every frame / on mood update:
        nucleo.update_mood("ENERGETIC")

        # On shutdown:
        nucleo.stop()
    """

    def __init__(self, auto_detect=True):
        port         = find_nucleo_port() if auto_detect else SERIAL_PORT
        self.port    = port
        self.baud    = SERIAL_BAUDRATE
        self.ser     = None
        self.running = False
        self.thread  = None

        self._lock        = threading.Lock()
        self._mood        = "CALM"
        self._connected   = False
        self._warned_once = False

        # Reader thread — listens for ACK from Nucleo (optional)
        self._reader_thread = None

    # ── Connection ────────────────────────────────────────────────────────────

    def _connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            # Give the Nucleo 1.5s to boot after connection (STLink resets the MCU)
            time.sleep(1.5)
            self._connected   = True
            self._warned_once = False
            print(f"  [hardware] Connected to Nucleo on {self.port} @ {self.baud} baud")
        except serial.SerialException as e:
            self.ser        = None
            self._connected = False
            if not self._warned_once:
                print(f"  [hardware] Cannot open {self.port}: {e}")
                print(f"  [hardware] Check SERIAL_PORT in config.py and that the Nucleo is plugged in.")
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
        Builds the standard mood message:
        "MOOD,R,G,B,SIDE\n"
        """
        r, g, b = MOOD_RGB[mood]
        r       = int(r * RED_CHANNEL_SCALE)
        side    = MOOD_SIDE[mood]
        return f"{mood},{r},{g},{b},{side}\n"

    def _beat_message(self):
        """
        Beat flash: full white, all 4 sides.
        "BEAT,255,255,255,15\n"
        The Nucleo should flash white for ~200ms then return to mood color.
        """
        return "BEAT,255,255,255,15\n"

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
        Sends a BEAT flash first, then updates the mood color.
        The Nucleo should show white for ~200ms then settle into the mood color.
        """
        print(f"  [hardware] Track change → mood={mood}  🎵  {track_name} — {artist}")

        # 1. Send beat flash
        self._send(self._beat_message())

        # 2. Short pause so the Nucleo can show the flash
        time.sleep(0.25)

        # 3. Update to new mood color
        self.update_mood(mood)
        self._send(self._mood_message(mood))

    # ── Background send loop ──────────────────────────────────────────────────

    def _send_loop(self):
        """
        Runs in a background thread.
        Sends the current mood message every SERIAL_INTERVAL seconds (50ms).
        This keeps the Nucleo in sync even if a packet is dropped.
        """
        while self.running:
            with self._lock:
                mood = self._mood
            self._send(self._mood_message(mood))
            time.sleep(SERIAL_INTERVAL)

    # ── Optional: read ACK from Nucleo ────────────────────────────────────────

    def _reader_loop(self):
        """
        Reads lines sent back from the Nucleo (e.g. "ACK\n" or "ERROR\n").
        This is optional — the Nucleo firmware doesn't have to send anything back.
        Useful during development to verify the Nucleo is receiving correctly.
        """
        while self.running:
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        print(f"  [Nucleo] ← {line}")
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

        print("  [hardware] NucleoController started")

    def stop(self):
        self.running = False
        time.sleep(0.1)
        self._disconnect()
        print("  [hardware] NucleoController stopped")


# ── Standalone test ───────────────────────────────────────────────────────────
# Run this file directly to test the hardware connection without the DJ pipeline.
# It cycles through all 4 moods with a beat flash between each.

if __name__ == "__main__":
    print("═" * 55)
    print("  Nucleo Hardware Test — cycles through all moods")
    print("  Press Ctrl+C to stop")
    print("═" * 55 + "\n")

    nucleo = NucleoController(auto_detect=True)
    nucleo.start()

    moods = ["CALM", "WARM", "ENERGETIC", "HYPE"]

    try:
        for cycle in range(2):          # run 2 full cycles
            for mood in moods:
                print(f"\n  Testing mood: {mood}")
                nucleo.on_track_change(mood, track_name=f"Test track ({mood})")
                time.sleep(4)           # hold each mood for 4 seconds

        print("\n  Test complete.")

    except KeyboardInterrupt:
        print("\n  Interrupted by user.")

    finally:
        nucleo.stop()