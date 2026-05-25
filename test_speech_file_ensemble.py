import sys
import joblib
import librosa
import numpy as np

import torch
import torch.nn as nn
import torchaudio


# =========================
# MODEL PATHS
# =========================

CNN_MODEL_PATH = "models/speech_command_cnn.pt"
DTW_MODEL_PATH = "models/speech_command_model_v3_dtw.pkl"


# =========================
# ENSEMBLE CONFIG
# =========================

CNN_CONF_THRESHOLD = 0.65
DTW_DISTANCE_THRESHOLD = 0.85

TOP_K_DTW = 5


# =========================
# CNN MODEL
# Phải giống kiến trúc lúc train cnn_v2
# =========================

class SmallAudioCNN(nn.Module):
    def __init__(self, num_classes):
        super().__init__()

        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),

            nn.AdaptiveAvgPool2d((1, 1))
        )

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.4),
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x


# =========================
# CNN FUNCTIONS
# =========================

def load_audio_for_cnn(file_path, sample_rate, duration):
    num_samples = int(sample_rate * duration)

    audio, sr = librosa.load(
        file_path,
        sr=sample_rate,
        mono=True
    )

    if len(audio) == 0:
        audio = np.zeros(num_samples, dtype=np.float32)

    # Cắt khoảng lặng đầu/cuối
    audio, _ = librosa.effects.trim(audio, top_db=25)

    if len(audio) == 0:
        audio = np.zeros(num_samples, dtype=np.float32)

    # Normalize âm lượng
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val

    # Pad/cut về đúng độ dài train
    if len(audio) < num_samples:
        audio = np.pad(audio, (0, num_samples - len(audio)))
    else:
        audio = audio[:num_samples]

    waveform = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)

    return waveform


def waveform_to_logmel(waveform, sample_rate, n_mels):
    mel_transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=sample_rate,
        n_fft=1024,
        hop_length=256,
        n_mels=n_mels
    )

    db_transform = torchaudio.transforms.AmplitudeToDB()

    logmel = mel_transform(waveform)
    logmel = db_transform(logmel)

    mean = logmel.mean()
    std = logmel.std() + 1e-8

    logmel = (logmel - mean) / std

    return logmel


def load_cnn_model():
    checkpoint = torch.load(CNN_MODEL_PATH, map_location="cpu")

    class_names = checkpoint["class_names"]
    sample_rate = checkpoint["sample_rate"]
    duration = checkpoint["duration"]
    n_mels = checkpoint["n_mels"]

    model = SmallAudioCNN(num_classes=len(class_names))
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    return model, class_names, sample_rate, duration, n_mels


def predict_cnn(audio_path, model, class_names, sample_rate, duration, n_mels):
    waveform = load_audio_for_cnn(
        audio_path,
        sample_rate=sample_rate,
        duration=duration
    )

    logmel = waveform_to_logmel(
        waveform,
        sample_rate=sample_rate,
        n_mels=n_mels
    )

    x = logmel.unsqueeze(0)

    with torch.no_grad():
        logits = model(x)
        probs = torch.softmax(logits, dim=1)[0]

    top_idx = int(torch.argmax(probs))
    pred_class = class_names[top_idx]
    confidence = float(probs[top_idx])

    sorted_scores = sorted(
        zip(class_names, probs.tolist()),
        key=lambda x: x[1],
        reverse=True
    )

    return pred_class, confidence, sorted_scores


# =========================
# DTW FUNCTIONS
# =========================

def load_audio_for_dtw(file_path, sample_rate=16000, max_duration=3.0):
    audio, sr = librosa.load(
        file_path,
        sr=sample_rate,
        mono=True
    )

    audio, _ = librosa.effects.trim(audio, top_db=25)

    if len(audio) == 0:
        audio = np.zeros(int(sample_rate * max_duration), dtype=np.float32)

    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val

    max_len = int(sample_rate * max_duration)

    if len(audio) > max_len:
        audio = audio[:max_len]

    return audio


def extract_mfcc_sequence_for_dtw(
    file_path,
    sample_rate=16000,
    n_mfcc=40,
    max_duration=3.0
):
    audio = load_audio_for_dtw(
        file_path,
        sample_rate=sample_rate,
        max_duration=max_duration
    )

    mfcc = librosa.feature.mfcc(
        y=audio,
        sr=sample_rate,
        n_mfcc=n_mfcc
    )

    delta = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)

    features = np.vstack([mfcc, delta, delta2])

    mean = np.mean(features, axis=1, keepdims=True)
    std = np.std(features, axis=1, keepdims=True) + 1e-8

    features = (features - mean) / std

    return features


def dtw_distance(a, b):
    D, wp = librosa.sequence.dtw(
        X=a,
        Y=b,
        metric="cosine"
    )

    distance = D[-1, -1] / len(wp)

    return float(distance)


def load_dtw_model():
    model_data = joblib.load(DTW_MODEL_PATH)
    return model_data


def predict_dtw(audio_path, model_data):
    sample_rate = model_data.get("sample_rate", 16000)
    n_mfcc = model_data.get("n_mfcc", 40)

    test_features = extract_mfcc_sequence_for_dtw(
        audio_path,
        sample_rate=sample_rate,
        n_mfcc=n_mfcc,
        max_duration=3.0
    )

    distances = []

    for sample in model_data["samples"]:
        dist = dtw_distance(test_features, sample["features"])

        distances.append({
            "label": sample["label"],
            "path": sample["path"],
            "distance": dist
        })

    distances = sorted(distances, key=lambda x: x["distance"])

    nearest = distances[0]
    top_matches = distances[:TOP_K_DTW]

    pred_class = nearest["label"]
    nearest_distance = nearest["distance"]

    if nearest_distance > DTW_DISTANCE_THRESHOLD:
        final_class = "unknown"
    else:
        final_class = pred_class

    return pred_class, final_class, nearest_distance, nearest, top_matches


# =========================
# ENSEMBLE LOGIC
# =========================

def ensemble_predict(audio_path):
    # Load CNN
    cnn_model, cnn_class_names, cnn_sr, cnn_duration, cnn_n_mels = load_cnn_model()

    # CNN predict
    cnn_pred, cnn_conf, cnn_scores = predict_cnn(
        audio_path,
        cnn_model,
        cnn_class_names,
        cnn_sr,
        cnn_duration,
        cnn_n_mels
    )

    # Nếu CNN đủ chắc thì dùng CNN
    if cnn_conf >= CNN_CONF_THRESHOLD:
        return {
            "final_class": cnn_pred,
            "used_model": "cnn",
            "cnn_pred": cnn_pred,
            "cnn_confidence": cnn_conf,
            "cnn_scores": cnn_scores,
            "dtw_pred": None,
            "dtw_distance": None,
            "dtw_top_matches": []
        }

    # Nếu CNN không chắc thì fallback DTW
    dtw_model_data = load_dtw_model()

    dtw_pred, dtw_final, dtw_distance_value, dtw_nearest, dtw_top_matches = predict_dtw(
        audio_path,
        dtw_model_data
    )

    return {
        "final_class": dtw_final,
        "used_model": "dtw_fallback",
        "cnn_pred": cnn_pred,
        "cnn_confidence": cnn_conf,
        "cnn_scores": cnn_scores,
        "dtw_pred": dtw_pred,
        "dtw_distance": dtw_distance_value,
        "dtw_nearest": dtw_nearest,
        "dtw_top_matches": dtw_top_matches
    }


def main():
    if len(sys.argv) < 2:
        print("Cách dùng:")
        print("python test_speech_file_ensemble.py path/to/audio.mp3")
        return

    audio_path = sys.argv[1]

    result = ensemble_predict(audio_path)

    print("\n========== AUDIO ==========")
    print("Audio:", audio_path)

    print("\n========== FINAL RESULT ==========")
    print("Final class:", result["final_class"])
    print("Used model:", result["used_model"])

    print("\n========== CNN RESULT ==========")
    print("CNN predicted:", result["cnn_pred"])
    print("CNN confidence:", round(result["cnn_confidence"], 3))

    print("\nCNN scores:")
    for cls, score in result["cnn_scores"]:
        print(f"{cls}: {score:.3f}")

    if result["used_model"] == "dtw_fallback":
        print("\n========== DTW FALLBACK RESULT ==========")
        print("DTW predicted:", result["dtw_pred"])
        print("DTW nearest distance:", round(result["dtw_distance"], 3))

        print("\nDTW top matched files:")
        for item in result["dtw_top_matches"]:
            print(
                item["label"],
                round(item["distance"], 3),
                item["path"]
            )


if __name__ == "__main__":
    main()
