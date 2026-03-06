import os
import numpy as np
import pickle
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
from music21 import converter, note, chord, stream, tempo

# --- 1. SETTINGS FROM PARSE_MIDI.PY ---
# This must match your training data grid
GRID = 0.25 

def quantize(duration):
    """Snaps a duration to the nearest grid point as defined in parse_midi.py."""
    return round(duration / GRID) * GRID

# --- 2. MANUAL ARCHITECTURE BUILDER ---
def build_model_architecture(vocab_size, sequence_length):
    """Rebuilds the model structure from train_model.py."""
    model = Sequential([
        LSTM(512, return_sequences=True, input_shape=(sequence_length, 1)),
        Dropout(0.4),
        LSTM(512, return_sequences=True),
        Dropout(0.4),
        LSTM(256),
        Dropout(0.3),
        Dense(256, activation='relu'),
        Dense(vocab_size, activation='softmax')
    ])
    return model

# --- 3. SEED EXTRACTION ---
def extract_seed_from_midi(midi_path, note_to_int, sequence_length):
    try:
        score = converter.parse(midi_path)
        extracted = []

        for element in score.flatten().notesAndRests:
            # Matches the format: f"{pitch}_{final_duration}" from parse_midi.py
            duration = quantize(element.duration.quarterLength)
            if duration <= 0: continue

            if isinstance(element, note.Note):
                tag = f"{element.pitch}_{duration}"
            elif isinstance(element, chord.Chord):
                pitches = ".".join(str(n) for n in element.pitches)
                tag = f"{pitches}_{duration}"
            elif isinstance(element, note.Rest):
                tag = f"rest_{duration}"
            else:
                continue
            extracted.append(tag)

        # Ensure seed notes exist in the model's vocabulary
        extracted = [n for n in extracted if n in note_to_int]

        if len(extracted) < sequence_length:
            return None

        start = np.random.randint(0, len(extracted) - sequence_length)
        return [note_to_int[n] for n in extracted[start:start + sequence_length]]
    except:
        return None

# --- 4. SAMPLING & GENERATION ---
def sample_with_top_k_top_p(preds, temperature=0.9):
    preds = np.asarray(preds).astype("float64")
    preds = np.log(preds + 1e-9) / temperature
    preds = np.exp(preds)
    preds /= np.sum(preds)
    return np.random.choice(len(preds), p=preds)

def generate_song(model, note_to_int, int_to_note, max_value, seed_folder, num_notes, temperature):
    sequence_length = 100 
    midi_files = [f for f in os.listdir(seed_folder) if f.lower().endswith(".mid")]
    
    pattern = None
    if midi_files:
        for _ in range(15): # Attempt to find a valid seed
            seed_file = os.path.join(seed_folder, np.random.choice(midi_files))
            pattern = extract_seed_from_midi(seed_file, note_to_int, sequence_length)
            if pattern: 
                print(f"Using seed from: {os.path.basename(seed_file)}")
                break
    
    if pattern is None:
        print("⚠ No valid seed files found. Using random seed.")
        pattern = list(np.random.randint(0, len(note_to_int), sequence_length))

    prediction_output = []
    for step in range(num_notes):
        input_seq = np.reshape(pattern, (1, sequence_length, 1)) / float(max_value)
        prediction = model.predict(input_seq, verbose=0)[0]
        
        index = sample_with_top_k_top_p(prediction, temperature)
        note_str = int_to_note[index]
        prediction_output.append(note_str)
        
        # Display every note as it is generated
        print(f"Note {step+1}/{num_notes}: {note_str}")
        
        pattern.append(index)
        pattern = pattern[1:]

    return prediction_output

# --- 5. MIDI CONVERSION ---
def convert_to_midi(prediction_output, output_path):
    output_stream = stream.Stream()
    offset = 0

    for pattern in prediction_output:
        try:
            # Split the pitch/chord and duration
            parts = pattern.split('_')
            note_data = parts[0]
            duration = float(parts[1]) if len(parts) > 1 else 0.25

            if "." in note_data: # Chord
                notes = [note.Note(n) for n in note_data.split(".")]
                new_obj = chord.Chord(notes)
            elif note_data == "rest":
                new_obj = note.Rest()
            else: # Single Note
                new_obj = note.Note(note_data)

            new_obj.offset = offset
            new_obj.duration.quarterLength = duration
            output_stream.append(new_obj)
            offset += duration 
        except Exception:
            continue

    output_stream.write("midi", fp=output_path)

# --- 6. EXECUTION ---
def run():
    BASE = r"C:\Users\warty\OneDrive\Desktop\Python_projects\Song-training-test"
    DATA_DIR = os.path.join(BASE, "model_data")
    
    with open(os.path.join(DATA_DIR, "note_to_int.pkl"), "rb") as f:
        n2i = pickle.load(f)
    with open(os.path.join(DATA_DIR, "int_to_note.pkl"), "rb") as f:
        i2n = pickle.load(f)
    max_val = np.load(os.path.join(DATA_DIR, "max_note_value.npy"))

    print("Building model and loading weights...")
    model = build_model_architecture(len(n2i), 100)
    model.load_weights(os.path.join(DATA_DIR, "music_model_final.h5"))

    out_folder = os.path.join(BASE, "generated_songs")
    os.makedirs(out_folder, exist_ok=True)

    # Generate 5 songs as requested
    num_songs = 5
    for i in range(num_songs):
        print(f"\n--- Generating Song {i+1} of {num_songs} ---")
        notes = generate_song(model, n2i, i2n, max_val, os.path.join(BASE, "chopin"), 400, 0.9)
        output_file = os.path.join(out_folder, f"composition_{i+1}.mid")
        convert_to_midi(notes, output_file)
        print(f"Saved: {output_file}")

if __name__ == "__main__":
    run()