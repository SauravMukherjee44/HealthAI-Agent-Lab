import importlib.util
import wave
from io import BytesIO

import numpy as np

from .config import Settings

MEDICAL_KEYTERMS = (
    "angina,arrhythmia,blood pressure,breathlessness,cholesterol,diabetes,"
    "dizziness,fatigue,glucose,hypertension,insulin,nausea,palpitations,"
    "shortness of breath"
)


class VoiceUnavailable(RuntimeError):
    pass


class InvalidAudio(ValueError):
    pass


class MoonshineTranscriber:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None

    @property
    def available(self) -> bool:
        return bool(
            self.settings.moonshine_cache_dir
            and self.settings.moonshine_cache_dir.is_dir()
            and importlib.util.find_spec("moonshine_voice")
        )

    def _load_model(self):
        if self._model is not None:
            return self._model
        if not self.available:
            raise VoiceUnavailable("Moonshine ASR is not installed on this environment yet.")
        try:
            from moonshine_voice import Transcriber, get_model_for_language

            model_path, model_arch = get_model_for_language("en", self.settings.moonshine_model_arch)
            self._model = Transcriber(
                model_path=model_path,
                model_arch=model_arch,
                options={"keyterms": MEDICAL_KEYTERMS, "keyterm_boost": "2.0"},
            )
        except Exception as exc:
            raise VoiceUnavailable("Moonshine ASR could not load its bundled model.") from exc
        return self._model

    def _decode_wav(self, content: bytes) -> np.ndarray:
        if len(content) > self.settings.max_audio_bytes:
            raise InvalidAudio("Audio must be smaller than 2 MB.")
        try:
            with wave.open(BytesIO(content), "rb") as recording:
                channels = recording.getnchannels()
                sample_width = recording.getsampwidth()
                sample_rate = recording.getframerate()
                frame_count = recording.getnframes()
                if channels != 1 or sample_width != 2 or sample_rate != 16_000:
                    raise InvalidAudio("Use 16 kHz mono 16-bit PCM WAV audio.")
                if frame_count == 0:
                    raise InvalidAudio("The recording is empty.")
                if frame_count / sample_rate > self.settings.max_audio_seconds:
                    raise InvalidAudio("Audio must be 30 seconds or shorter.")
                frames = recording.readframes(frame_count)
        except (wave.Error, EOFError) as exc:
            raise InvalidAudio("The uploaded file is not a valid WAV recording.") from exc
        return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0

    def transcribe(self, content: bytes) -> str:
        audio = self._decode_wav(content)
        try:
            result = self._load_model().transcribe_without_streaming(audio.tolist(), sample_rate=16_000, flags=0)
        except VoiceUnavailable:
            raise
        except Exception as exc:
            raise VoiceUnavailable("Moonshine transcription failed on this deployment.") from exc
        transcript = " ".join(line.text.strip() for line in result.lines if line.text.strip())
        if not transcript:
            raise InvalidAudio("No speech was detected.")
        return transcript
