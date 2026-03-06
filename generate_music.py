import os
import numpy as np
import pickle
import tensorflow as tf
from tensorflow.keras.models import load_model
from music21 import converter, note, chord, stream, interval, pitch

# --- 1. SETTINGS ---
GRID = 0.25 
SEQUENCE_LENGTH = 100 

def quantize(duration):
    return round(duration / GRID) * GRID

# --- 2. SEED EXTRACTION ---
def transpose_score_to_c_or_a(score):
    """Normalizes the key of the seed file to match training data."""
    try:
        key = score.analyze('key')
        if key.mode == "major":
            target_tonic = pitch.Pitch('C')
        elif key.mode == "minor":
            target_tonic = pitch.Pitch('A')
        else:
            return score
        itvl = interval.Interval(key.tonic, target_tonic)
        return score.transpose(itvl)
    except:
        return score

def extract_seed_from_midi(midi_path, note_to_int):
    try:
        score = converter.parse(midi_path)
        score = transpose_score_to_c_or_a(score)
        extracted = []

        for element in score.flatten().notesAndRests:
            duration = quantize(element.duration.quarterLength)
            if duration <= 0: continue

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

        # Filter out notes not in the model's vocabulary
        extracted = [n for n in extracted if n in note_to_int]

        if len(extracted) < SEQUENCE_LENGTH:
            print(f"Seed file too short ({len(extracted)} notes). Need {SEQUENCE_LENGTH}.")
            return None

        start = np.random.randint(0, len(extracted) - SEQUENCE_LENGTH)
        return [note_to_int[n] for n in extracted[start:start + SEQUENCE_LENGTH]]
    except Exception as e:
        print(f"Failed to extract seed: {e}")
        return None

# --- 3. GENERATION LOGIC ---
def sample_with_temp(preds, temperature=0.5):
    """Weighted sampling to avoid repetitive 'robotic' music."""
    if temperature <= 0: return np.argmax(preds)
    preds = np.asarray(preds).astype('float64')
    preds = np.log(preds + 1e-7) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)

def generate_song(model, note_to_int, int_to_note, seed_file_path, num_notes, temperature):
    pattern = None
    if seed_file_path and os.path.exists(seed_file_path):
        print(f"Extracting seed from: {os.path.basename(seed_file_path)}")
        pattern = extract_seed_from_midi(seed_file_path, note_to_int)
    
    if pattern is None:
        print("Using random seed instead...")
        pattern = list(np.random.randint(0, len(note_to_int), SEQUENCE_LENGTH))

    prediction_output = []
    print("Generating notes...")
    for step in range(num_notes):
        # We pass integers directly because of the Embedding layer
        input_seq = np.reshape(pattern, (1, SEQUENCE_LENGTH)) 
        prediction = model.predict(input_seq, verbose=0)[0]
        
        idx = sample_with_temp(prediction, temperature)
        note_str = int_to_note[idx]
        prediction_output.append(note_str)

        pattern.append(idx)
        pattern = pattern[1:]
        
        if (step + 1) % 50 == 0:
            print(f"Generated {step + 1}/{num_notes}...")

    return prediction_output

# --- 4. MIDI CONVERSION ---
def convert_to_midi(prediction_output, output_path):
    output_stream = stream.Stream()
    offset = 0
    for pattern in prediction_output:
        try:
            parts = pattern.split('_')
            note_data = parts[0]
            duration = float(parts[1])
            if "." in note_data: # Chord
                new_obj = chord.Chord(note_data.split("."))
            elif note_data == "rest":
                new_obj = note.Rest()
            else: # Single Note
                new_obj = note.Note(note_data)
            new_obj.offset = offset
            new_obj.duration.quarterLength = duration
            output_stream.append(new_obj)
            offset += duration 
        except: continue
    output_stream.write("midi", fp=output_path)

# --- 5. EXECUTION ---
def run():
    # --- LOCAL PATHS ---
    BASE = r"C:\Users\warty\OneDrive\Desktop\Python_projects\Song-training-test"
    DATA_DIR = os.path.join(BASE, "model_data")
    
    # Path to the file you downloaded from Colab
    model_file = os.path.join(DATA_DIR, "music_model_200.h5")
    n2i_file = os.path.join(DATA_DIR, "note_to_int.pkl")
    
    if not os.path.exists(model_file):
        print(f"ERROR: Model file not found at {model_file}")
        return

    # Load Vocabulary
    with open(n2i_file, "rb") as f:
        n2i = pickle.load(f)
    i2n = {i: n for n, i in n2i.items()}

    print("Loading model from file (this may take a moment)...")
    # Using load_model avoids architecture mismatch errors
    model = load_model(model_file)

    out_folder = os.path.join(BASE, "generated_songs")
    os.makedirs(out_folder, exist_ok=True)

    # Path to your local MIDI seed
    seed_file = os.path.join(BASE, "Jerry_Lee_Lewis_-_Great_Balls_of_Fire.mid")
    
    notes = generate_song(model, n2i, i2n, seed_file, 400, 0.5)
    
    output_file = os.path.join(out_folder, "composition.mid")
    convert_to_midi(notes, output_file)
    print(f"\nSUCCESS! Saved to: {output_file}")

if __name__ == "__main__":
    run()