# serial_formatter.py

import threading
import time
import serial
from config import (
    SERIAL_PORT,
    SERIAL_BAUDRATE,
    SERIAL_INTERVAL,
    MOOD_RGB,
    MOOD_SIDE,
    RED_CHANNEL_SCALE,
)


class SerialFormatter:
    def __init__(self):
        self.ser         = None
        self.running     = False
        self.thread      = None
        self.latest_mood = "CALM"
        self.latest_amp  = 0.0
        self._connected  = False

    def connect(self):
        try:
            self.ser = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=1)
            if not self._connected:
                print(f"  [serial] Connected to {SERIAL_PORT} at {SERIAL_BAUDRATE} baud")
                self._connected = True
        except serial.SerialException as e:
            if self._connected or self.ser is None:
                # Only print once — avoids spamming the console every 50 ms
                print(f"  [serial] Could not open {SERIAL_PORT}: {e}")
                print(f"  [serial] Check SERIAL_PORT in config.py. LED output is disabled.")
                self._connected = False
            self.ser = None

    def update_state(self, mood, amp):
        self.latest_mood = mood
        self.latest_amp  = amp

    def _build_message(self):
        r, g, b = MOOD_RGB[self.latest_mood]
        r       = int(r * RED_CHANNEL_SCALE)
        side    = MOOD_SIDE[self.latest_mood]
        return f"{self.latest_mood},{self.latest_amp:.2f},{r},{g},{b},{side}\n"

    def _send_loop(self):
        warned = False
        while self.running:
            if self.ser is None or not self.ser.is_open:
                self.connect()

            msg = self._build_message()

            if self.ser and self.ser.is_open:
                try:
                    self.ser.write(msg.encode("utf-8"))
                    warned = False
                except Exception as e:
                    if not warned:
                        print(f"  [serial] Write failed: {e}. Reconnecting...")
                        warned = True
                    try:
                        self.ser.close()
                    except Exception:
                        pass
                    self.ser = None

            time.sleep(SERIAL_INTERVAL)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread  = threading.Thread(target=self._send_loop, daemon=True)
        self.thread.start()
        print("  [serial] Sender thread started")

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        print("  [serial] Stopped")