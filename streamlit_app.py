import streamlit as st
import random
import librosa
import librosa.display
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from recommendation_engine import RecommendationEngine, GeminiExplainer
import os
import io
import pickle
import tempfile
from pathlib import Path
from collections import Counter
import re
import soundfile as sf

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="SoniqueAI",
    layout="wide",
    page_icon="🎧"
)

# Initialize recommendation engine
@st.cache_resource
def load_recommendation_engine():
    """Load and cache the recommendation engine from the fixed CSVs.

    This version assumes the two files are present in the repository root
    and makes no attempt to upload alternative datasets.  If they are missing
    an exception will be raised so the problem is obvious during development.
    """
    script_dir = Path(__file__).resolve().parent
    cwd_dir = Path.cwd().resolve()

    # Prefer genre-enriched music info file; check both script dir and cwd.
    music_candidates = [
        script_dir / "Music_Info_genre_present.csv",
        cwd_dir / "Music_Info_genre_present.csv",
        script_dir / "Music Info.csv",
        cwd_dir / "Music Info.csv",
    ]

    # Listening history filename can vary by execution context, so probe both.
    history_candidates = [
        script_dir / "User Listening History.csv",
        cwd_dir / "User Listening History.csv",
    ]

    music_info = next((p for p in music_candidates if p.exists()), None)
    listening_history = next((p for p in history_candidates if p.exists()), None)

    if music_info is None or listening_history is None:
        checked_music = ", ".join(str(p) for p in music_candidates)
        checked_history = ", ".join(str(p) for p in history_candidates)
        raise FileNotFoundError(
            f"Missing dataset files. Checked music files: [{checked_music}] | "
            f"Checked listening history files: [{checked_history}]"
        )

    return RecommendationEngine(str(music_info.resolve()), str(listening_history.resolve()))

@st.cache_resource
def load_gemini_explainer():
    """Load Gemini explainer if API key is available"""
    api_key = st.secrets.get("GEMINI_API_KEY", None) if hasattr(st, 'secrets') else None
    return GeminiExplainer(api_key)

def find_midi_directory():
    """Find the project's MIDI folder across local and cloud execution directories."""
    script_dir = Path(__file__).resolve().parent
    cwd_dir = Path.cwd().resolve()

    explicit_candidates = [
        # User-provided local directory
        Path(r"c:\Users\warty\OneDrive\Desktop\Python_projects\Song-training-test\Midi_files"),
        # Streamlit Cloud mount paths
        Path("/mount/src/song-training-test/Midi_files"),
        Path("/mount/src/song-training-test/midi_files"),
    ]

    env_hint = os.getenv("MIDI_FILES_DIR")
    if env_hint:
        explicit_candidates.insert(0, Path(env_hint))

    for candidate in explicit_candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    search_roots = [script_dir, cwd_dir, script_dir.parent, cwd_dir.parent]
    midi_dir = None

    for root in search_roots:
        for folder_name in ("Midi_files", "midi_files", "MIDI_files"):
            candidate = root / folder_name
            if candidate.exists() and candidate.is_dir():
                midi_dir = candidate
                break
        if midi_dir is not None:
            break

    if midi_dir is None:
        for root in search_roots:
            if not root.exists() or not root.is_dir():
                continue
            for child in root.iterdir():
                if child.is_dir() and child.name.lower() == "midi_files":
                    midi_dir = child
                    break
            if midi_dir is not None:
                break

    return midi_dir

def get_midi_search_locations():
    """Return all MIDI folder locations checked for troubleshooting."""
    script_dir = Path(__file__).resolve().parent
    cwd_dir = Path.cwd().resolve()

    locations = [
        os.getenv("MIDI_FILES_DIR", ""),
        r"c:\Users\warty\OneDrive\Desktop\Python_projects\Song-training-test\Midi_files",
        "/mount/src/song-training-test/Midi_files",
        "/mount/src/song-training-test/midi_files",
        str(script_dir / "Midi_files"),
        str(cwd_dir / "Midi_files"),
        str(script_dir.parent / "Midi_files"),
        str(cwd_dir.parent / "Midi_files"),
    ]

    return [loc for loc in locations if loc]

def get_midi_track_map():
    """Return mapping of MIDI filename -> absolute path."""
    midi_dir = find_midi_directory()
    if midi_dir is None:
        return {}

    midi_files = [
        midi_file for midi_file in midi_dir.rglob("*")
        if midi_file.is_file() and midi_file.suffix.lower() in {".mid", ".midi"}
    ]

    track_map = {}
    for midi_file in sorted(midi_files):
        key_name = midi_file.name
        if key_name in track_map:
            key_name = str(midi_file.relative_to(midi_dir)).replace("\\", "/")
        track_map[key_name] = str(midi_file.resolve())
    return track_map

def load_midi_tracks():
    """Return available MIDI song names from the local Midi_files folder."""
    return sorted(get_midi_track_map().keys())

GRID = 0.25
SEQUENCE_LENGTH = 100
MODEL_NOTES_DEFAULT = 400
SYNTH_SAMPLE_RATE = 22050
GENERATION_LOADER_CACHE_VERSION = "2026-03-13-legacy-loader-fix"

@st.cache_resource
def load_generation_assets(cache_version=GENERATION_LOADER_CACHE_VERSION):
    """Load generation model and token mappings used by generate_music.py logic."""
    # Cache version busts stale Streamlit cache entries after loader updates.
    _ = cache_version
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "model_data"

    model_file = data_dir / "music_model_200.h5"
    mapping_file = data_dir / "note_to_int.pkl"

    if not model_file.exists():
        return None, f"Model file missing: {model_file}"
    if not mapping_file.exists():
        return None, f"Mapping file missing: {mapping_file}"

    try:
        with open(mapping_file, "rb") as f:
            note_to_int = pickle.load(f)
        int_to_note = {i: n for n, i in note_to_int.items()}
    except Exception as exc:
        return None, f"Failed loading token mapping: {exc}"

    model = None
    load_errors = []

    # Try multiple model loaders because cloud runtimes can differ in Keras/H5 compatibility.
    try:
        from tensorflow.keras.models import load_model
        model = load_model(str(model_file), compile=False)
    except Exception as exc:
        load_errors.append(f"Primary model loader failed: {exc}")

    if model is None:
        try:
            from keras.models import load_model as keras_load_model
            model = keras_load_model(str(model_file), compile=False, safe_mode=False)
        except Exception as exc:
            load_errors.append(f"Keras fallback loader failed: {exc}")

    if model is None:
        try:
            import h5py
            import json
            from tensorflow.keras.models import model_from_json

            with h5py.File(str(model_file), "r") as h5f:
                model_config = h5f.attrs.get("model_config")
                if isinstance(model_config, bytes):
                    model_config = model_config.decode("utf-8")
                model_config = json.loads(model_config)

            def patch_input_layer_config(node):
                if isinstance(node, dict):
                    if node.get("class_name") == "InputLayer":
                        cfg = node.get("config", {})
                        if "batch_shape" in cfg and "batch_input_shape" not in cfg:
                            cfg["batch_input_shape"] = cfg.pop("batch_shape")
                    for value in node.values():
                        patch_input_layer_config(value)
                elif isinstance(node, list):
                    for item in node:
                        patch_input_layer_config(item)

            def patch_dtype_policy_config(node):
                if isinstance(node, dict):
                    cfg = node.get("config")
                    if isinstance(cfg, dict) and isinstance(cfg.get("dtype"), dict):
                        dtype_cfg = cfg.get("dtype", {})
                        if dtype_cfg.get("class_name") == "DTypePolicy":
                            cfg["dtype"] = dtype_cfg.get("config", {}).get("name", "float32")
                    for value in node.values():
                        patch_dtype_policy_config(value)
                elif isinstance(node, list):
                    for item in node:
                        patch_dtype_policy_config(item)

            patch_input_layer_config(model_config)
            patch_dtype_policy_config(model_config)
            model = model_from_json(json.dumps(model_config))
            model.load_weights(str(model_file))
        except Exception as exc:
            load_errors.append(f"Legacy H5 compatibility loader failed: {exc}")

    if model is None:
        try:
            import h5py
            from tensorflow.keras.layers import InputLayer, Embedding, LSTM, Dropout, Dense
            from tensorflow.keras.models import model_from_json

            with h5py.File(str(model_file), "r") as h5f:
                model_config = h5f.attrs.get("model_config")
                if isinstance(model_config, bytes):
                    model_config = model_config.decode("utf-8")

            model = model_from_json(
                model_config,
                custom_objects={
                    "InputLayer": InputLayer,
                    "Embedding": Embedding,
                    "LSTM": LSTM,
                    "Dropout": Dropout,
                    "Dense": Dense,
                },
            )
            model.load_weights(str(model_file))
        except Exception as exc:
            load_errors.append(f"Custom-object compatibility loader failed: {exc}")

    load_warning = None if model is not None else " | ".join(load_errors)

    return {
        "model": model,
        "note_to_int": note_to_int,
        "int_to_note": int_to_note,
        "load_warning": load_warning,
    }, None

def quantize(duration):
    return round(duration / GRID) * GRID

def transpose_score_to_c_or_a(score):
    """Normalize seed score key to C major / A minor."""
    try:
        from music21 import interval, pitch
        key = score.analyze('key')
        if key.mode == "major":
            target_tonic = pitch.Pitch('C')
        elif key.mode == "minor":
            target_tonic = pitch.Pitch('A')
        else:
            return score
        itvl = interval.Interval(key.tonic, target_tonic)
        return score.transpose(itvl)
    except Exception:
        return score

def extract_seed_from_midi(seed_path_1, seed_path_2, note_to_int):
    """Mirror seed extraction behavior from generate_music.py for remix seeding."""
    try:
        from music21 import converter, note, chord
    except Exception:
        return None

    midi_files = [seed_path_1, seed_path_2]
    for path in midi_files:
        if not path or not os.path.exists(path):
            continue

        try:
            score = converter.parse(path)
            score = transpose_score_to_c_or_a(score)
            extracted = []

            for element in score.flatten().notesAndRests:
                duration = quantize(element.duration.quarterLength)
                if duration <= 0:
                    continue

                if isinstance(element, note.Note):
                    tag = f"{element.pitch}_{duration}"
                elif isinstance(element, chord.Chord):
                    pitches = ".".join(str(p) for p in sorted(element.pitches))
                    tag = f"{pitches}_{duration}"
                elif isinstance(element, note.Rest) and duration >= 0.5:
                    tag = f"rest_{duration}"
                else:
                    continue
                extracted.append(tag)

            extracted = [n for n in extracted if n in note_to_int]
            if len(extracted) < SEQUENCE_LENGTH:
                continue

            start = np.random.randint(0, len(extracted) - SEQUENCE_LENGTH)
            return [note_to_int[n] for n in extracted[start:start + SEQUENCE_LENGTH]]
        except Exception:
            continue

    return None

def sample_with_temp(preds, temperature=0.5):
    """Weighted sampling to avoid repetitive notes."""
    if temperature <= 0:
        return int(np.argmax(preds))

    preds = np.asarray(preds).astype('float64')
    preds = np.log(preds + 1e-7) / max(temperature, 1e-6)
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return int(np.argmax(probas))

def generate_song_with_model(model, note_to_int, int_to_note, seed_file_path_1, seed_file_path_2, num_notes, temperature):
    """Generate symbolic notes using model logic aligned with generate_music.py."""
    pattern = None
    if seed_file_path_1 and seed_file_path_2 and os.path.exists(seed_file_path_1) and os.path.exists(seed_file_path_2):
        pattern = extract_seed_from_midi(seed_file_path_1, seed_file_path_2, note_to_int)
    if pattern is None:
        pattern = list(np.random.randint(0, len(note_to_int), SEQUENCE_LENGTH))

    prediction_output = []
    for _ in range(num_notes):
        input_seq = np.reshape(pattern, (1, SEQUENCE_LENGTH))
        prediction = model.predict(input_seq, verbose=0)[0]
        idx = sample_with_temp(prediction, temperature)
        note_str = int_to_note.get(idx)
        if note_str is None:
            continue

        prediction_output.append(note_str)
        pattern.append(idx)
        pattern = pattern[1:]

    return prediction_output

def generate_song_without_model(note_to_int, int_to_note, seed_file_path_1, seed_file_path_2, num_notes):
    """Fallback generation when model loading fails in constrained runtimes."""
    pattern = None
    if seed_file_path_1 and seed_file_path_2 and os.path.exists(seed_file_path_1) and os.path.exists(seed_file_path_2):
        pattern = extract_seed_from_midi(seed_file_path_1, seed_file_path_2, note_to_int)
    if pattern is None:
        pattern = list(np.random.randint(0, len(note_to_int), SEQUENCE_LENGTH))

    prediction_output = []
    for _ in range(num_notes):
        idx = int(pattern[-1] if pattern else np.random.randint(0, len(note_to_int)))
        # Small random walk around the current token for smoother transitions.
        step = int(np.random.choice([-3, -2, -1, 0, 1, 2, 3]))
        idx = max(0, min(idx + step, len(int_to_note) - 1))
        note_str = int_to_note.get(idx)
        if note_str is None:
            continue

        prediction_output.append(note_str)
        pattern.append(idx)
        pattern = pattern[1:]

    return prediction_output

def convert_to_midi(prediction_output, output_path):
    """Convert generated note tokens to a MIDI file — matches generate_music.py logic."""
    from music21 import note, chord, stream
    output_stream = stream.Stream()
    offset = 0
    for pattern in prediction_output:
        try:
            parts = pattern.split('_')
            note_data = parts[0]
            duration = float(parts[1])
            if "." in note_data:
                new_obj = chord.Chord(note_data.split("."))
            elif note_data == "rest":
                new_obj = note.Rest()
            else:
                new_obj = note.Note(note_data)
            new_obj.offset = offset
            new_obj.duration.quarterLength = duration
            output_stream.append(new_obj)
            offset += duration
        except Exception:
            continue
    output_stream.write("midi", fp=output_path)

def parse_note_token_to_hz(token):
    """Convert model note token to frequency in Hz."""
    token = str(token).strip()
    if not token:
        return None

    try:
        if token.isdigit():
            return float(librosa.midi_to_hz(int(token)))
        return float(librosa.note_to_hz(token))
    except Exception:
        return None

def synthesize_prediction_audio(prediction_output, tempo_bpm=120.0, sample_rate=SYNTH_SAMPLE_RATE):
    """Render generated symbolic notes to playable waveform for Streamlit audio."""
    seconds_per_quarter = 60.0 / max(tempo_bpm, 1.0)
    chunks = []

    for pattern in prediction_output:
        if "_" not in pattern:
            continue

        note_data, duration_str = pattern.rsplit("_", 1)
        try:
            quarter_len = max(float(duration_str), GRID)
        except Exception:
            quarter_len = GRID

        event_seconds = quarter_len * seconds_per_quarter
        n_samples = max(int(event_seconds * sample_rate), 1)
        t = np.linspace(0, event_seconds, n_samples, endpoint=False)

        if note_data == "rest":
            chunk = np.zeros(n_samples, dtype=np.float32)
        else:
            freqs = [
                parse_note_token_to_hz(token)
                for token in str(note_data).split(".")
            ]
            freqs = [f for f in freqs if f is not None]

            if not freqs:
                chunk = np.zeros(n_samples, dtype=np.float32)
            else:
                wave = np.zeros_like(t, dtype=np.float32)
                for freq in freqs:
                    wave += np.sin(2 * np.pi * float(freq) * t).astype(np.float32)

                wave /= max(len(freqs), 1)
                attack_len = max(int(0.01 * sample_rate), 1)
                release_len = max(int(0.02 * sample_rate), 1)
                env = np.ones(n_samples, dtype=np.float32)
                env[:attack_len] = np.linspace(0, 1, attack_len, dtype=np.float32)
                env[-release_len:] = np.linspace(1, 0, release_len, dtype=np.float32)
                chunk = wave * env * 0.25

        chunks.append(chunk)

    if not chunks:
        return np.zeros(sample_rate, dtype=np.float32)

    audio = np.concatenate(chunks).astype(np.float32)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0:
        audio = audio / peak * 0.9
    return audio

def audio_to_wav_bytes(audio_wave, sample_rate=SYNTH_SAMPLE_RATE):
    """Encode waveform as WAV bytes, always returning plain bytes."""
    try:
        buffer = io.BytesIO()
        sf.write(buffer, audio_wave, sample_rate, format="WAV")
        buffer.seek(0)
        return bytes(buffer.read())
    except Exception:
        # Pure-Python fallback: build a minimal PCM WAV header without soundfile.
        pcm = np.clip(audio_wave, -1.0, 1.0)
        pcm16 = (pcm * 32767.0).astype(np.int16)
        pcm_bytes = pcm16.tobytes()
        data_len = len(pcm_bytes)
        header = (
            b'RIFF' + (data_len + 36).to_bytes(4, 'little') +
            b'WAVE' +
            b'fmt ' + (16).to_bytes(4, 'little') +
            (1).to_bytes(2, 'little') +          # PCM
            (1).to_bytes(2, 'little') +          # mono
            sample_rate.to_bytes(4, 'little') +  # sample rate
            (sample_rate * 2).to_bytes(4, 'little') +  # byte rate
            (2).to_bytes(2, 'little') +          # block align
            (16).to_bytes(2, 'little') +         # bits per sample
            b'data' + data_len.to_bytes(4, 'little')
        )
        return bytes(header + pcm_bytes)

def audio_to_mp3_bytes(audio_wave, sample_rate=SYNTH_SAMPLE_RATE):
    """Encode waveform as MP3 bytes using lameenc when available."""
    try:
        import lameenc
    except Exception as exc:
        return None, f"MP3 encoder unavailable ({exc}). Install 'lameenc' to enable MP3 downloads."

    pcm16 = np.clip(audio_wave, -1.0, 1.0)
    pcm16 = (pcm16 * 32767.0).astype(np.int16)

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(192)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(1)
    encoder.set_quality(2)

    mp3_data = encoder.encode(pcm16.tobytes())
    mp3_data += encoder.flush()
    # Ensure plain bytes — some lameenc versions return bytearray which
    # Streamlit's download_button rejects on certain runtime versions.
    return bytes(mp3_data), None

def build_generated_song_bundle(seed_file_1=None, seed_file_2=None, num_notes=MODEL_NOTES_DEFAULT, temperature=1.0, render_tempo_bpm=120.0):
    """Generate notes from model and package playable/downloadable audio artifacts."""
    assets, load_err = load_generation_assets()
    if assets is None:
        return None, load_err

    model = assets.get("model")
    if model is None:
        return None, "Generation model is unavailable in this runtime."

    notes = generate_song_with_model(
        model,
        assets["note_to_int"],
        assets["int_to_note"],
        seed_file_1,
        seed_file_2,
        int(num_notes),
        float(temperature),
    )

    if not notes:
        return None, "Model generation returned no notes."

    audio_wave = synthesize_prediction_audio(notes, tempo_bpm=render_tempo_bpm, sample_rate=SYNTH_SAMPLE_RATE)
    wav_bytes = audio_to_wav_bytes(audio_wave, sample_rate=SYNTH_SAMPLE_RATE)
    mp3_bytes, mp3_error = audio_to_mp3_bytes(audio_wave, sample_rate=SYNTH_SAMPLE_RATE)

    midi_bytes = None
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tmp:
            tmp_path = tmp.name
        convert_to_midi(notes, tmp_path)
        with open(tmp_path, "rb") as f:
            midi_bytes = bytes(f.read())
        os.remove(tmp_path)
    except Exception:
        pass

    return {
        "notes": notes,
        "audio_wave": audio_wave,
        "wav_bytes": wav_bytes,
        "mp3_bytes": mp3_bytes,
        "mp3_error": mp3_error,
        "midi_bytes": midi_bytes,
    }, None

def estimate_key_mode(chroma_mean):
    """Estimate musical key and mode from an averaged chroma profile."""
    key_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

    chroma_vector = np.array(chroma_mean, dtype=float)
    if chroma_vector.shape[0] != 12:
        return "Unknown", "Unknown"

    major_scores = [np.dot(chroma_vector, np.roll(major_profile, i)) for i in range(12)]
    minor_scores = [np.dot(chroma_vector, np.roll(minor_profile, i)) for i in range(12)]

    best_major_idx = int(np.argmax(major_scores))
    best_minor_idx = int(np.argmax(minor_scores))

    if major_scores[best_major_idx] >= minor_scores[best_minor_idx]:
        return key_names[best_major_idx], "major"
    return key_names[best_minor_idx], "minor"

def analyze_audio_features(y, sr):
    """Compute song-level audio stats used across preprocessing and UI."""
    duration_sec = float(librosa.get_duration(y=y, sr=sr))

    tempo_estimate, _ = librosa.beat.beat_track(y=y, sr=sr)
    if isinstance(tempo_estimate, np.ndarray):
        tempo_bpm = float(tempo_estimate.squeeze()) if tempo_estimate.size else 0.0
    else:
        tempo_bpm = float(tempo_estimate)

    rms = librosa.feature.rms(y=y)
    energy = float(np.mean(rms))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y=y)))
    centroids = librosa.feature.spectral_centroid(y=y, sr=sr)
    centroid_mean = float(np.mean(np.abs(centroids)))

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = float(np.mean(np.abs(mfcc)))

    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    chroma_mean_scalar = float(np.mean(np.abs(chroma)))

    amplitude = np.maximum(np.abs(y), 1e-9)
    loudness = float(np.mean(librosa.amplitude_to_db(amplitude, ref=1.0)))

    key_name, mode_name = estimate_key_mode(chroma_mean)

    return {
        "duration_sec": duration_sec,
        "sample_rate": int(sr),
        "tempo": tempo_bpm,
        "energy": energy,
        "loudness": loudness,
        "zcr": zcr,
        "centroid_mean": centroid_mean,
        "mfcc_mean": mfcc_mean,
        "chroma_mean": chroma_mean_scalar,
        "key": key_name,
        "mode": mode_name,
    }

def infer_mood_and_instruments(stats):
    """Simple rule-based labels from extracted audio features."""
    tempo = stats["tempo"]
    energy = stats["energy"]
    centroid = stats["centroid_mean"]
    zcr = stats["zcr"]

    if tempo >= 130 and energy >= 0.08:
        mood = "Energetic"
    elif tempo <= 90 and energy <= 0.04:
        mood = "Calm"
    elif stats["mode"] == "minor":
        mood = "Moody"
    else:
        mood = "Balanced"

    if centroid >= 2500 and zcr >= 0.08:
        instruments = "Likely drums/percussion + bright synths"
    elif centroid <= 1200:
        instruments = "Likely piano/strings + low-mid instruments"
    else:
        instruments = "Likely mixed band setup (guitar/keys/vocals)"

    return mood, instruments

# Initialize feedback database (in-memory for demo)
@st.cache_resource
def initialize_feedback_db():
    """Initialize feedback database with sample data"""
    feedback_db = {
        'tracks': {},  # {track_id: {'name': str, 'artist': str, 'ratings': [1-5], 'moods': [], 'comments': []}}
        'user_profiles': {}  # {user_id: {'avatar': str, 'feedback_count': int}}
    }
    return feedback_db

def get_recommendation_runtime():
    """Load recommendation engine lazily so app startup remains lightweight."""
    try:
        return load_recommendation_engine(), None
    except Exception as exc:
        return None, str(exc)

# Lightweight globals only
gemini_explainer = load_gemini_explainer()
feedback_db = initialize_feedback_db()


# Helper functions for feedback system
def parse_mood_from_text(text):
    """Extract mood keywords from user comments"""
    mood_keywords = {
        'happy': ['happy', 'joy', 'cheerful', 'uplifting', 'energetic', 'excited'],
        'sad': ['sad', 'melancholy', 'depressed', 'heartbroken', 'down'],
        'calm': ['calm', 'peaceful', 'relaxing', 'soothing', 'mellow', 'chill'],
        'energetic': ['energetic', 'upbeat', 'intense', 'powerful', 'aggressive'],
        'romantic': ['romantic', 'love', 'beautiful', 'dreamy', 'intimate'],
        'neutral': []
    }
    
    text_lower = text.lower()
    detected_moods = []
    
    for mood, keywords in mood_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            detected_moods.append(mood)
    
    return detected_moods if detected_moods else ['neutral']

def extract_suggestions(text):
    """Extract actionable suggestions from comments"""
    patterns = [
        r'(?:should|could|wish|want|need|might|try|add|improve|change|fix|remove)\s+(.{10,50})',
        r'(?:more|less)\s+(.{10,50})',
        r'(?:like|similar to|remind me of)\s+(.{10,50})',
    ]
    
    suggestions = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        suggestions.extend(matches)
    
    return [s.strip() for s in suggestions if len(s.strip()) > 3]

def load_feedback_from_history(engine):
    """Create a feedback-like structure using listening history.

    The app used to manufacture fake comments and ratings.  We now leverage the
    real CSV that lives in the repo; playcounts are treated as ratings and no
    textual feedback is available.
    """
    feedback = {}
    if engine is None or engine.listening_df is None:
        return feedback

    for track_id, group in engine.listening_df.groupby('track_id'):
        track_info = engine.music_df[engine.music_df['track_id'] == track_id]
        if not track_info.empty:
            row = track_info.iloc[0]
            name = row.get('name', track_id)
            artist = row.get('artist', 'Unknown')
        else:
            name = track_id
            artist = 'Unknown'

        ratings = group['playcount'].tolist()
        feedback[track_id] = {
            'name': name,
            'artist': artist,
            'ratings': ratings,
            'comments': [],
            'moods': [],
            'suggestions': []
        }
    return feedback

# derive feedback lazily in pages that need recommendation data
sample_feedback = {}

# Mood colors for consistent visualization
MOOD_COLORS = {
    'happy': '#FFD700',
    'sad': '#4169E1',
    'calm': '#98FB98',
    'energetic': '#FF6347',
    'romantic': '#FF69B4',
    'neutral': '#A9A9A9'
}

# -----------------------------
# STYLE
# -----------------------------
st.markdown("""
<style>
.stApp{
background: radial-gradient(circle at top,#0f0f1a,#050509);
color:white;
}

h1{
font-size:60px;
text-align:center;
background:linear-gradient(90deg,#7b5cff,#00c6ff,#ff4d8d,#ff9a3c);
-webkit-background-clip:text;
-webkit-text-fill-color:transparent;
}

.stButton>button{
background:linear-gradient(90deg,#7b5cff,#ff4d8d,#ff9a3c);
color:white;
border-radius:10px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# TITLE
# -----------------------------
st.markdown("""
<h1>🎧 SoniqueAI</h1>
<p style='text-align:center'>AI Music Creation & Insights Platform</p>
""", unsafe_allow_html=True)

# -----------------------------
# SIDEBAR
# -----------------------------
st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Home",
        "Remix / Compose Studio",
        "Recommendations",
        "Mood & Instrument Analyzer",
        "Analytics Dashboard"
    ]
)

# -----------------------------
# HOME
# -----------------------------
if page == "Home":

    st.header("Welcome to SoniqueAI")

    st.write("""
This platform allows you to:

• Generate AI music  
• Remix songs  
• Analyze moods and instruments  
• Receive recommendations  
• Explore music analytics
""")

# -----------------------------
# REMIX / COMPOSE STUDIO
# -----------------------------
elif page == "Remix / Compose Studio":

    st.header("🎼 Remix / Compose Studio")

    mode = st.radio(
        "Mode",
        ["Compose (AI Generated)", "Remix Songs"]
    )

    midi_track_map = get_midi_track_map()
    midi_dataset = sorted(midi_track_map.keys())

    # COMPOSE
    if mode == "Compose (AI Generated)":

        st.write("Generate music from the trained model logic in generate_music.py")

        comp_col1, comp_col2, comp_col3 = st.columns(3)
        with comp_col1:
            compose_num_notes = st.slider("Generated Notes", 120, 800, MODEL_NOTES_DEFAULT, key="compose_num_notes")
        with comp_col2:
            compose_temperature = 1.0
            st.caption("Temperature is fixed at 1.0")
        with comp_col3:
            compose_tempo = st.slider("Playback Tempo (BPM)", 70, 180, 120, key="compose_tempo")

        if st.button("Generate Composition"):
            with st.spinner("Generating composition from model..."):
                bundle, err = build_generated_song_bundle(
                    num_notes=compose_num_notes,
                    temperature=compose_temperature,
                    render_tempo_bpm=float(compose_tempo),
                )
            if err:
                st.error(f"Generation failed: {err}")
            else:
                st.session_state["compose_song_bundle"] = bundle
                st.success("Composition generated successfully.")

        compose_bundle = st.session_state.get("compose_song_bundle")
        if compose_bundle:
            st.subheader("Generated Composition")
            # Use pre-encoded WAV bytes for st.audio — compatible with all Streamlit versions.
            _compose_wav = compose_bundle.get("wav_bytes")
            if _compose_wav:
                st.audio(_compose_wav, format="audio/wav")

            _mp3 = compose_bundle.get("mp3_bytes")
            _wav = compose_bundle.get("wav_bytes")
            if _mp3 and isinstance(_mp3, bytes) and len(_mp3) > 0:
                st.download_button(
                    "Download Composition (MP3)",
                    data=_mp3,
                    file_name="composition.mp3",
                    mime="audio/mpeg",
                    key="compose_mp3_download",
                )
            elif _wav and isinstance(_wav, bytes) and len(_wav) > 0:
                if compose_bundle.get("mp3_error"):
                    st.warning(compose_bundle["mp3_error"])
                st.download_button(
                    "Download Composition (WAV)",
                    data=_wav,
                    file_name="composition.wav",
                    mime="audio/wav",
                    key="compose_wav_download",
                )
            else:
                st.warning("Audio export unavailable — no valid bytes to download.")
            _compose_mid = compose_bundle.get("midi_bytes")
            if _compose_mid and isinstance(_compose_mid, bytes) and len(_compose_mid) > 0:
                st.download_button(
                    "Download Composition (MIDI)",
                    data=_compose_mid,
                    file_name="composition.mid",
                    mime="audio/midi",
                    key="compose_midi_download",
                )

    # REMIX
    if mode == "Remix Songs":

        if not midi_dataset:
            st.info("⚠️ No MIDI songs found in the Midi_files folder.")
            with st.expander("Checked MIDI directories"):
                for checked_path in get_midi_search_locations():
                    st.write(f"- {checked_path}")
                st.caption("Set MIDI_FILES_DIR in environment variables to override the folder path.")

            st.subheader("Upload Two MIDI Files for Remix")
            up_col1, up_col2 = st.columns(2)
            with up_col1:
                uploaded_midi_1 = st.file_uploader(
                    "Upload Track 1 MIDI",
                    type=["mid", "midi"],
                    key="uploaded_remix_track_1"
                )
                blend = st.slider("Blend Ratio", 0.0, 1.0, 0.5, key="uploaded_blend")
            with up_col2:
                uploaded_midi_2 = st.file_uploader(
                    "Upload Track 2 MIDI",
                    type=["mid", "midi"],
                    key="uploaded_remix_track_2"
                )
                tempo = st.slider("Tempo Adjustment", 0.5, 2.0, 1.0, key="uploaded_tempo")

            if st.button("Create Remix from Uploads", key="create_remix_uploads"):
                if uploaded_midi_1 is None or uploaded_midi_2 is None:
                    st.error("Please upload two MIDI files.")
                elif uploaded_midi_1.name == uploaded_midi_2.name:
                    st.error("Track 1 and Track 2 must be different songs.")
                else:
                    temp_paths = []
                    try:
                        for uploaded in (uploaded_midi_1, uploaded_midi_2):
                            suffix = Path(uploaded.name).suffix or ".mid"
                            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                                tmp_file.write(uploaded.getvalue())
                                temp_paths.append(tmp_file.name)

                        generation_temp = 1.0
                        render_bpm = 120.0 * float(tempo)

                        with st.spinner("Generating remix from uploaded MIDI files..."):
                            bundle, err = build_generated_song_bundle(
                                seed_file_1=temp_paths[0],
                                seed_file_2=temp_paths[1],
                                num_notes=MODEL_NOTES_DEFAULT,
                                temperature=generation_temp,
                                render_tempo_bpm=render_bpm,
                            )

                        if err:
                            st.error(f"Remix generation failed: {err}")
                        else:
                            st.session_state["remix_song_bundle"] = bundle
                            st.success("Remixed uploaded MIDI tracks.")
                    finally:
                        for temp_path in temp_paths:
                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass

            remix_bundle = st.session_state.get("remix_song_bundle")
            if remix_bundle:
                st.subheader("Generated Remix")
                _remix_wav = remix_bundle.get("wav_bytes")
                if _remix_wav:
                    st.audio(_remix_wav, format="audio/wav")

                _rmp3 = remix_bundle.get("mp3_bytes")
                _rwav = remix_bundle.get("wav_bytes")
                if _rmp3 and isinstance(_rmp3, bytes) and len(_rmp3) > 0:
                    st.download_button(
                        "Download Remix (MP3)",
                        data=_rmp3,
                        file_name="remix.mp3",
                        mime="audio/mpeg",
                        key="remix_mp3_download_uploaded",
                    )
                elif _rwav and isinstance(_rwav, bytes) and len(_rwav) > 0:
                    if remix_bundle.get("mp3_error"):
                        st.warning(remix_bundle["mp3_error"])
                    st.download_button(
                        "Download Remix (WAV)",
                        data=_rwav,
                        file_name="remix.wav",
                        mime="audio/wav",
                        key="remix_wav_download_uploaded",
                    )
                else:
                    st.warning("Audio export unavailable — no valid bytes to download.")
                _remix_mid_up = remix_bundle.get("midi_bytes")
                if _remix_mid_up and isinstance(_remix_mid_up, bytes) and len(_remix_mid_up) > 0:
                    st.download_button(
                        "Download Remix (MIDI)",
                        data=_remix_mid_up,
                        file_name="remix.mid",
                        mime="audio/midi",
                        key="remix_midi_download_uploaded",
                    )
        else:
            col1, col2 = st.columns(2)

            with col1:
                track1 = st.selectbox("Track 1", midi_dataset, key="remix_track_1")
                blend = st.slider("Blend Ratio", 0.0, 1.0, 0.5)

            track2_options = [song for song in midi_dataset if song != track1]

            with col2:
                if not track2_options:
                    st.warning("Need at least two MIDI songs to create a remix.")
                    track2 = None
                else:
                    track2 = st.selectbox("Track 2", track2_options, key="remix_track_2")
                tempo = st.slider("Tempo Adjustment", 0.5, 2.0, 1.0)

            if st.button("Create Remix"):
                if track2 is None:
                    st.error("Please add at least two MIDI songs to the Midi_files folder.")
                elif track1 == track2:
                    st.error("Track 1 and Track 2 must be different songs.")
                else:
                    seed_1 = midi_track_map.get(track1)
                    seed_2 = midi_track_map.get(track2)

                    generation_temp = 1.0
                    render_bpm = 120.0 * float(tempo)

                    with st.spinner("Generating remix from selected MIDI seeds..."):
                        bundle, err = build_generated_song_bundle(
                            seed_file_1=seed_1,
                            seed_file_2=seed_2,
                            num_notes=MODEL_NOTES_DEFAULT,
                            temperature=generation_temp,
                            render_tempo_bpm=render_bpm,
                        )

                    if err:
                        st.error(f"Remix generation failed: {err}")
                    else:
                        st.session_state["remix_song_bundle"] = bundle
                        st.success(f"Remixed {track1} and {track2}")

            remix_bundle = st.session_state.get("remix_song_bundle")
            if remix_bundle:
                st.subheader("Generated Remix")
                _remix_wav2 = remix_bundle.get("wav_bytes")
                if _remix_wav2:
                    st.audio(_remix_wav2, format="audio/wav")
                _rmp3b = remix_bundle.get("mp3_bytes")
                _rwavb = remix_bundle.get("wav_bytes")
                if _rmp3b and isinstance(_rmp3b, bytes) and len(_rmp3b) > 0:
                    st.download_button(
                        "Download Remix (MP3)",
                        data=_rmp3b,
                        file_name="remix.mp3",
                        mime="audio/mpeg",
                        key="remix_mp3_download",
                    )
                elif _rwavb and isinstance(_rwavb, bytes) and len(_rwavb) > 0:
                    if remix_bundle.get("mp3_error"):
                        st.warning(remix_bundle["mp3_error"])
                    st.download_button(
                        "Download Remix (WAV)",
                        data=_rwavb,
                        file_name="remix.wav",
                        mime="audio/wav",
                        key="remix_wav_download",
                    )
                else:
                    st.warning("Audio export unavailable — no valid bytes to download.")
                _remix_mid = remix_bundle.get("midi_bytes")
                if _remix_mid and isinstance(_remix_mid, bytes) and len(_remix_mid) > 0:
                    st.download_button(
                        "Download Remix (MIDI)",
                        data=_remix_mid,
                        file_name="remix.mid",
                        mime="audio/midi",
                        key="remix_midi_download",
                    )

# -----------------------------
# RECOMMENDATIONS
# -----------------------------
elif page == "Recommendations":

    st.header("🎧 Music Recommendations Engine")

    rec_engine, load_error = get_recommendation_runtime()

    if rec_engine is None:
        msg = "❌ Recommendation engine not initialized. "
        if load_error:
            msg += f"(Load error: {load_error})"
        st.error(msg)
    else:
        # Get available users
        available_users = rec_engine.get_all_user_ids()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # User Selection
            st.subheader("1. Select User")
            user_input = st.selectbox(
                "Choose a user or enter user ID",
                options=["Enter custom ID"] + available_users[:100],
                key="user_select"
            )
            
            if user_input == "Enter custom ID":
                user_id = st.text_input("Enter User ID")
            else:
                user_id = user_input
        
        with col2:
            # Recommendation Method
            st.subheader("2. Recommendation Method")
            method = st.radio(
                "Choose filtering approach",
                ["Hybrid (Recommended)", "Collaborative Filtering", "Content-Based Filtering"]
            )
            
            top_n = st.slider("Number of recommendations", 3, 10, 5)
        
        # Get User Preferences
        if st.button("🔍 Get Recommendations", key="get_recs"):
            if not user_id:
                st.warning("⚠️ Please enter or select a user ID")
            else:
                with st.spinner("🎵 Finding personalized recommendations..."):
                    
                    # Get recommendations based on selected method
                    if method == "Hybrid (Recommended)":
                        recommendations = rec_engine.hybrid_recommendations(user_id, top_n=top_n)
                    elif method == "Collaborative Filtering":
                        recommendations = rec_engine.collaborative_filtering(user_id, top_n=top_n)
                    else:
                        recommendations = rec_engine.content_based_filtering(user_id, top_n=top_n)
                    
                    # Get user preferences
                    user_prefs = rec_engine.get_user_preferences(user_id)
                    
                    if not recommendations:
                        st.warning("⚠️ No recommendations found for this user. Try a different user ID.")
                    else:
                        # Display User Profile
                        st.success(f"✅ Found {len(recommendations)} recommendations for User: {user_id}")
                        
                        if user_prefs:
                            st.subheader("👤 Your Music Profile")
                            
                            pref_col1, pref_col2, pref_col3, pref_col4 = st.columns(4)
                            
                            with pref_col1:
                                st.metric("Songs Listened", user_prefs['total_songs_listened'])
                            with pref_col2:
                                st.metric("Avg Energy", f"{user_prefs['avg_energy']:.2f}")
                            with pref_col3:
                                st.metric("Avg Happiness", f"{user_prefs['avg_valence']:.2f}")
                            with pref_col4:
                                st.metric("Avg Danceability", f"{user_prefs['avg_danceability']:.2f}")
                            
                            # Visualize User Preferences
                            vis_col1, vis_col2 = st.columns(2)
                            
                            with vis_col1:
                                st.subheader("📊 Your Audio Profile")
                                fig, ax = plt.subplots(figsize=(8, 5))
                                
                                features = ['Energy', 'Happiness\n(Valence)', 'Danceability', 'Acousticness']
                                values = [
                                    user_prefs['avg_energy'],
                                    user_prefs['avg_valence'],
                                    user_prefs['avg_danceability'],
                                    user_prefs['avg_acousticness']
                                ]
                                
                                bars = ax.bar(features, values, color=['#ff4d8d', '#00c6ff', '#7b5cff', '#ff9a3c'])
                                ax.set_ylim(0, 1)
                                ax.set_ylabel('Score')
                                ax.grid(axis='y', alpha=0.3)
                                
                                for bar in bars:
                                    height = bar.get_height()
                                    ax.text(bar.get_x() + bar.get_width()/2., height,
                                           f'{height:.2f}', ha='center', va='bottom', fontsize=9)
                                
                                plt.tight_layout()
                                st.pyplot(fig)
                            
                            with vis_col2:
                                st.subheader("🎵 Top Genres")
                                if user_prefs['favorite_genres']:
                                    genre_data = user_prefs['favorite_genres']
                                    genres = list(genre_data.keys())[:5]
                                    counts = list(genre_data.values())[:5]
                                    
                                    fig, ax = plt.subplots(figsize=(8, 5))
                                    ax.barh(genres, counts, color='#7b5cff')
                                    ax.set_xlabel('Number of Songs')
                                    ax.grid(axis='x', alpha=0.3)
                                    plt.tight_layout()
                                    st.pyplot(fig)
                                else:
                                    st.info("No genre information available")
                        
                        # Display Recommendations
                        st.subheader(f"🎧 Top {len(recommendations)} Recommendations")
                        
                        for idx, rec in enumerate(recommendations, 1):
                            with st.expander(f"#{idx} - {rec['name']} by {rec['artist']}"):
                                col1, col2 = st.columns([2, 1])
                                
                                with col1:
                                    st.write(f"**Track ID:** {rec['track_id']}")
                                    st.write(f"**Genre:** {rec['genre']}")
                                    st.write(f"**Method:** {rec['method'].title()}")
                                    
                                    # Generate explanation if Gemini is available
                                    if gemini_explainer and gemini_explainer.client:
                                        explanation = gemini_explainer.generate_explanation(rec, user_prefs)
                                        st.info(f"💡 Why recommended:\n\n{explanation}")
                                    else:
                                        explanation = gemini_explainer.generate_explanation(rec, user_prefs) if gemini_explainer else None
                                        if explanation:
                                            st.info(f"💡 Why recommended:\n\n{explanation}")
                                
                                with col2:
                                    st.write("**Audio Stats**")
                                    st.metric("Energy", f"{rec['energy']:.2f}")
                                    st.metric("Happiness", f"{rec['valence']:.2f}")
                                    st.metric("Dance", f"{rec['danceability']:.2f}")
                        
                        # Summary Statistics
                        st.subheader("📈 Recommendation Summary")
                        
                        summary_col1, summary_col2 = st.columns(2)
                        
                        with summary_col1:
                            st.write("**Methods Used:**")
                            method_counts = {}
                            for rec in recommendations:
                                method = rec['method']
                                method_counts[method] = method_counts.get(method, 0) + 1
                            
                            for method, count in method_counts.items():
                                st.write(f"- {method.title()}: {count} songs")
                        
                        with summary_col2:
                            st.write("**Average Features:**")
                            avg_energy = np.mean([r['energy'] for r in recommendations])
                            avg_valence = np.mean([r['valence'] for r in recommendations])
                            avg_dance = np.mean([r['danceability'] for r in recommendations])
                            
                            st.write(f"- Avg Energy: {avg_energy:.2f}")
                            st.write(f"- Avg Valence: {avg_valence:.2f}")
                            st.write(f"- Avg Danceability: {avg_dance:.2f}")

# -----------------------------
# MOOD & INSTRUMENT ANALYZER
# -----------------------------
elif page == "Mood & Instrument Analyzer":

    st.header("🎭 Mood & Instrument Analyzer")

    file = st.file_uploader(
        "Upload Song",
        type=["mp3", "wav", "ogg", "flac"]
    )

    if file is not None:
        st.audio(file)
        st.caption(f"Selected file: {file.name}")

        if st.button("Analyze Song"):
            file.seek(0)
            with st.spinner("Extracting song features and building mel spectrogram..."):
                y, sr = librosa.load(file, sr=None, mono=True)
                stats = analyze_audio_features(y, sr)
                detected_mood, detected_instruments = infer_mood_and_instruments(stats)
                mel = librosa.feature.melspectrogram(
                    y=y,
                    sr=sr,
                    n_fft=2048,
                    hop_length=512,
                    n_mels=128
                )
                mel_db = librosa.power_to_db(mel, ref=np.max)

            st.subheader("📈 Song Statistics")
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Tempo (BPM)", f"{stats['tempo']:.1f}")
            with m2:
                st.metric("Estimated Key", stats["key"])
            with m3:
                st.metric("Mode", stats["mode"].title())
            with m4:
                st.metric("Duration (sec)", f"{stats['duration_sec']:.1f}")

            s1, s2, s3, s4 = st.columns(4)
            with s1:
                st.metric("Energy (RMS)", f"{stats['energy']:.4f}")
            with s2:
                st.metric("Loudness (dB)", f"{stats['loudness']:.2f}")
            with s3:
                st.metric("MFCC Mean", f"{stats['mfcc_mean']:.2f}")
            with s4:
                st.metric("Chroma Mean", f"{stats['chroma_mean']:.2f}")

            with st.expander("More extracted stats"):
                st.write(f"Sample Rate: {stats['sample_rate']} Hz")
                st.write(f"Zero Crossing Rate: {stats['zcr']:.4f}")
                st.write(f"Spectral Centroid Mean: {stats['centroid_mean']:.2f}")

            st.subheader("🎨 Mel Spectrogram")
            fig, ax = plt.subplots(figsize=(10, 4))
            librosa.display.specshow(
                mel_db,
                sr=sr,
                hop_length=512,
                x_axis="time",
                y_axis="mel",
                ax=ax
            )
            ax.set_title("Mel Spectrogram")
            plt.tight_layout()
            st.pyplot(fig)

            st.subheader("🧠 Analyzer Inference")
            st.write(f"Detected Mood: {detected_mood}")
            st.write(f"Detected Instruments: {detected_instruments}")

# -----------------------------
# ANALYTICS
# -----------------------------
elif page == "Analytics Dashboard":

    st.header("📊 Interactive Analytics & Feedback Dashboard")

    rec_engine, load_error = get_recommendation_runtime()

    if rec_engine is None:
        msg = "❌ Analytics engine not initialized."
        if load_error:
            msg += f" (Load error: {load_error})"
        st.error(msg)
    else:
        st.subheader("📊 Dataset Statistics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("👥 Total Users", f"{len(rec_engine.get_all_user_ids()):,}")
        with col2:
            st.metric("🎵 Total Songs", f"{len(rec_engine.music_df):,}")
        with col3:
            st.metric("📊 Total Listens", f"{len(rec_engine.listening_df):,}")
        with col4:
            sparsity = (1 - len(rec_engine.listening_df) / (len(rec_engine.get_all_user_ids()) * len(rec_engine.music_df))) * 100
            st.metric("🔍 Sparsity", f"{sparsity:.1f}%")

        st.write("---")

        # Always-available chart from listening history.
        st.subheader("🔥 Most Played Tracks (Top 15)")
        top_tracks = (
            rec_engine.listening_df.groupby('track_id', as_index=False)['playcount']
            .sum()
            .sort_values('playcount', ascending=False)
            .head(15)
        )
        top_tracks = top_tracks.merge(
            rec_engine.music_df[['track_id', 'name']],
            on='track_id',
            how='left'
        )
        top_tracks['label'] = top_tracks['name'].fillna(top_tracks['track_id'])

        fig = px.bar(
            top_tracks,
            x='playcount',
            y='label',
            orientation='h',
            title='Top 15 Tracks by Total Playcount',
            labels={'playcount': 'Total Playcount', 'label': 'Track'}
        )
        fig.update_layout(height=500, showlegend=False, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

        st.write("---")

        st.subheader("🎼 Genre Distribution (Top 15)")
        if 'genre' in rec_engine.music_df.columns:
            genre_counts = rec_engine.music_df['genre'].value_counts().head(15)

            fig = px.bar(
                x=genre_counts.values,
                y=genre_counts.index,
                orientation='h',
                title='Top 15 Genres by Count',
                labels={'x': 'Number of Songs', 'y': 'Genre'},
                color=genre_counts.values,
                color_continuous_scale='Viridis'
            )
            fig.update_layout(height=500, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Genre column not available in music metadata.")

        st.write("---")

        st.subheader("🎚️ Audio Feature Distributions")

        feature_cols = ['energy', 'valence', 'danceability', 'acousticness']
        available_cols = [col for col in feature_cols if col in rec_engine.music_df.columns]

        if available_cols:
            selected_feature = st.selectbox(
                "Select feature to visualize",
                available_cols,
                key="feature_select"
            )

            feature_data = rec_engine.music_df[selected_feature].dropna()
            fig = px.histogram(
                x=feature_data,
                nbins=30,
                title=f'Distribution of {selected_feature.title()}',
                labels={'x': selected_feature.title(), 'count': 'Frequency'},
                color_discrete_sequence=['#7b5cff']
            )
            fig.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No audio feature columns found for distribution charts.")


