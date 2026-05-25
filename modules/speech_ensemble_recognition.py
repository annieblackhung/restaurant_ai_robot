import os
import tempfile
import sounddevice as sd
from scipy.io.wavfile import write

from test_speech_file_ensemble import ensemble_predict


class SpeechEnsembleRecognizer:
    def __init__(
        self,
        sample_rate=16000,
        duration=3.0
    ):
        self.sample_rate = sample_rate
        self.duration = duration

    def predict_file(self, audio_path):
        """
        Nhận diện lệnh từ file audio có sẵn.
        """
        result = ensemble_predict(audio_path)

        return {
            "intent": result["final_class"],
            "source": result["used_model"],
            "cnn_pred": result["cnn_pred"],
            "cnn_confidence": result["cnn_confidence"],
            "dtw_pred": result["dtw_pred"],
            "dtw_distance": result["dtw_distance"]
        }

    def record_audio(self):
        """
        Ghi âm từ microphone và lưu tạm thành file wav.
        """
        print("Đang nghe lệnh...")

        audio = sd.rec(
            int(self.duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32"
        )

        sd.wait()

        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        write(temp_file.name, self.sample_rate, audio)

        return temp_file.name

    def listen_and_predict(self):
        """
        Nghe trực tiếp từ microphone rồi nhận diện lệnh.
        """
        audio_path = self.record_audio()

        try:
            result = self.predict_file(audio_path)
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

        return result
