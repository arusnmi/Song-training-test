import os
import json
import pickle
import numpy as np

GRID = 0.25
SEQUENCE_LENGTH = 100


def quantize(duration):
    return round(duration / GRID) * GRID


def transpose_score_to_c_or_a(score):
    """Normalize the key of the seed score to C major or A minor."""
    try:
        from music21 import interval, pitch

        key = score.analyze("key")
        if key.mode == "major":
            target_tonic = pitch.Pitch("C")
        elif key.mode == "minor":
            target_tonic = pitch.Pitch("A")
        else:
            return score

        itvl = interval.Interval(key.tonic, target_tonic)
        return score.transpose(itvl)
    except Exception:
        return score


def extract_seed_from_midi(seed_path_1, seed_path_2, note_to_int):
    """Extract a model-ready seed sequence from one of two MIDI files."""
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
            return [note_to_int[n] for n in extracted[start : start + SEQUENCE_LENGTH]]
        except Exception:
            continue

    return None


def sample_with_temp(preds, temperature=0.5):
    """Weighted sampling for token generation."""
    if temperature <= 0:
        return int(np.argmax(preds))

    preds = np.asarray(preds).astype("float64")
    preds = np.log(preds + 1e-7) / max(temperature, 1e-6)
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return int(np.argmax(probas))


def load_note_mappings(mapping_file):
    """Load token mappings from pickle mapping file."""
    with open(mapping_file, "rb") as f:
        note_to_int = pickle.load(f)
    int_to_note = {i: n for n, i in note_to_int.items()}
    return note_to_int, int_to_note


def load_generation_model(model_file):
    """Load model with TensorFlow/Keras/H5 compatibility fallbacks."""
    model = None
    load_errors = []

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

            patch_input_layer_config(model_config)
            model = model_from_json(json.dumps(model_config))
            model.load_weights(str(model_file))
        except Exception as exc:
            load_errors.append(f"Legacy H5 compatibility loader failed: {exc}")

    # If any loader succeeded, suppress prior fallback errors caused by
    # legacy format differences so the app does not show a false failure.
    if model is not None:
        load_warning = None
    else:
        load_warning = " | ".join(load_errors) if load_errors else None
    return model, load_warning


def generate_song_with_model(
    model,
    note_to_int,
    int_to_note,
    seed_file_path_1,
    seed_file_path_2,
    num_notes,
    temperature,
):
    """Generate note tokens using the trained model."""
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
    """Fallback generation when model is unavailable."""
    pattern = None
    if seed_file_path_1 and seed_file_path_2 and os.path.exists(seed_file_path_1) and os.path.exists(seed_file_path_2):
        pattern = extract_seed_from_midi(seed_file_path_1, seed_file_path_2, note_to_int)

    if pattern is None:
        pattern = list(np.random.randint(0, len(note_to_int), SEQUENCE_LENGTH))

    prediction_output = []
    for _ in range(num_notes):
        idx = int(pattern[-1] if pattern else np.random.randint(0, len(note_to_int)))
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
    """Convert generated note tokens to a MIDI file."""
    from music21 import note, chord, stream

    output_stream = stream.Stream()
    offset = 0

    for pattern in prediction_output:
        try:
            parts = pattern.split("_")
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
