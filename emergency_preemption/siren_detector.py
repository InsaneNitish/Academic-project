"""
siren_detector.py

Audio-based siren detection using FFT analysis.
Detects Indian emergency vehicle siren frequency patterns (600-1600 Hz).

Note: Requires a microphone or video with audio track.
      Falls back gracefully if no audio input is available.
"""

import numpy as np
from collections import deque
from emergency_preemption import config

# Optional audio import
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False


class SirenDetector:
    """Detects emergency sirens from audio input using FFT."""

    def __init__(self, use_microphone=False):
        self.use_microphone = use_microphone and PYAUDIO_AVAILABLE
        self.audio_stream = None
        self.energy_history = deque(maxlen=30)
        self.siren_detected = False
        self.confidence = 0.0

        if self.use_microphone:
            try:
                self.pa = pyaudio.PyAudio()
                self.audio_stream = self.pa.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=config.AUDIO_SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=config.AUDIO_CHUNK_SIZE,
                    stream_callback=None
                )
                print("[SirenDetector] Microphone initialized.")
            except Exception as e:
                print(f"[SirenDetector] Microphone init failed: {e}")
                self.use_microphone = False
        else:
            if not PYAUDIO_AVAILABLE:
                print("[SirenDetector] PyAudio not installed. Audio detection disabled.")
            else:
                print("[SirenDetector] Microphone disabled. Using visual-only mode.")

    def analyze(self):
        """
        Analyze audio for siren frequencies.

        Returns:
            siren_detected (bool): Whether a siren is detected
            confidence (float): Detection confidence [0, 1]
            details (dict): Frequency analysis details
        """
        if not self.use_microphone or self.audio_stream is None:
            return False, 0.0, {"status": "audio_disabled"}

        try:
            # Read audio chunk
            audio_data = self.audio_stream.read(
                config.AUDIO_CHUNK_SIZE, exception_on_overflow=False)
            samples = np.frombuffer(audio_data, dtype=np.float32)

            # FFT Analysis
            fft = np.fft.rfft(samples)
            freqs = np.fft.rfftfreq(len(samples), 1.0 / config.AUDIO_SAMPLE_RATE)
            magnitudes = np.abs(fft) / len(samples)

            # Find energy in siren frequency band
            siren_band = (freqs >= config.SIREN_FREQ_LOW) & \
                         (freqs <= config.SIREN_FREQ_HIGH)
            siren_energy = np.sum(magnitudes[siren_band] ** 2)
            total_energy = np.sum(magnitudes ** 2) + 1e-10

            # Normalized siren energy
            siren_ratio = siren_energy / total_energy
            self.energy_history.append(siren_ratio)

            # Temporal analysis (siren has characteristic warble)
            avg_energy = np.mean(self.energy_history)
            energy_variance = np.var(self.energy_history)

            # Siren detected if sustained energy in siren band with warble
            self.siren_detected = (
                avg_energy > config.SIREN_ENERGY_THRESHOLD and
                energy_variance > 0.001  # Warble pattern
            )

            self.confidence = min(1.0, avg_energy / 0.1) if self.siren_detected else 0.0

            return self.siren_detected, self.confidence, {
                "status": "active",
                "siren_energy": round(siren_ratio, 4),
                "avg_energy": round(avg_energy, 4),
                "peak_freq": round(float(freqs[np.argmax(magnitudes)]), 1)
            }

        except Exception as e:
            return False, 0.0, {"status": f"error: {e}"}

    def release(self):
        """Release audio resources."""
        if self.audio_stream is not None:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
        if hasattr(self, 'pa'):
            self.pa.terminate()
