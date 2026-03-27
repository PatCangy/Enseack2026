# mixxx_bridge.py

class MixxxBridge:
    def __init__(self):
        self.queue = []

    def queue_track(self, filepath):
        if filepath:
            self.queue.append(filepath)
            print(f"[MIXXX] queued: {filepath}")

    def get_queue(self):
        return self.queue