import time
import numpy as np
import sounddevice as sd


class AudioCapture:
    def __init__(self, device=None, samplerate=44100, blocksize=2048):
        self.device = device
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.amplitude = 0.0
        self.stream = None

    def _audioCallback(self, indata, frames, timeInfo, status):
        # Print stream warnings if there are any
        if status:
            print(status)

        # Compute RMS amplitude from the current audio block
        rms = np.sqrt(np.mean(indata ** 2))
        self.amplitude = float(rms)

        # Print the current amplitude
        print(f"Amplitude: {self.amplitude:.6f}")

    def start(self):
        # Prevent starting more than one stream
        if self.stream is not None:
            return

        self.stream = sd.InputStream(
            device=self.device,
            channels=1,
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype="float32",
            callback=self._audioCallback
        )
        self.stream.start()

    def stop(self):
        # Stop and close the stream
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def get_amplitude(self):
        return self.amplitude


def chooseInputDevice():
    devices = sd.query_devices()
    inputDevices = []

    print("Available input devices:\n")

    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            inputDevices.append(i)
            print(f"{i}: {device['name']}")

    if not inputDevices:
        raise RuntimeError("No input devices found.")

    while True:
        try:
            choice = input("\nEnter the device number you want to use: ").strip()
            deviceIndex = int(choice)

            if deviceIndex in inputDevices:
                return deviceIndex
            else:
                print("That is not a valid input device number.")
        except ValueError:
            print("Please enter a valid number.")


if __name__ == "__main__":
    try:
        deviceIndex = chooseInputDevice()
        print(f"\nUsing device {deviceIndex}\n")
        print("Start playing audio now. Press Ctrl+C to stop.\n")

        audio = AudioCapture(device=deviceIndex)
        audio.start()

        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping audio capture...")
        audio.stop()
    except Exception as e:
        print(f"Error: {e}")