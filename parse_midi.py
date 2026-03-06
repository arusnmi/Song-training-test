import os
import json
import argparse
import numpy as np
import tensorflow.keras as keras
from music21 import converter, note, chord, interval, pitch

# Constants from the video series
GRID = 0.25 # 16th note steps
SEQUENCE_LENGTH = 64 # Equivalent to 4 bars of 4/4 music

# The list of acceptable durations as described in the videos
ACCEPTABLE_DURATIONS = [0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 4.0]

def is_acceptable_note(event):
    """
    Checks if a single note/rest has an acceptable duration.
    """
    return event.duration.quarterLength in ACCEPTABLE_DURATIONS

def transpose(score):
    """Transposes score to C Major / A Minor."""
    key = score.analyze('key')
    target_tonic = pitch.Pitch('C') if key.mode == "major" else pitch.Pitch('A')
    itvl = interval.Interval(key.tonic, target_tonic)
    return score.transpose(itvl)

def encode_song(song, time_step=GRID):
    """
    Converts a music21 score into a time-series string using 
    MIDI numbers and underscores. Skips individual notes with 
    non-conforming durations instead of skipping the entire song.
    """
    encoded_song = []
    for event in song.flatten().notesAndRests:
        # Skip individual notes that don't conform to acceptable durations
        if not is_acceptable_note(event):
            continue
            
        if isinstance(event, note.Note):
            symbol = event.pitch.midi
        elif isinstance(event, note.Rest):
            symbol = "R"
        else:
            continue

        steps = int(event.duration.quarterLength / time_step)
        for step in range(steps):
            if step == 0:
                encoded_song.append(str(symbol))
            else:
                encoded_song.append("_")
    
    return " ".join(encoded_song)

def preprocess(midi_dir):
    """
    Loads, transposes, and encodes all songs.
    Skips individual notes with non-conforming durations instead of entire songs.
    """
    songs = []
    for file in os.listdir(midi_dir):
        if file.endswith(".mid"):
            try:
                print(f"Parsing: {file}")
                score = converter.parse(os.path.join(midi_dir, file))
                score = transpose(score)
                encoded = encode_song(score)
                # Only add songs that have at least some valid notes
                if encoded.strip():
                    songs.append(encoded)
                else:
                    print(f"Skipping {file}: No conforming notes found.")
            except Exception as e:
                print(f"Error processing {file}: {e}")
                
    return songs

def create_single_file_dataset(songs, output_path, sequence_length):
    """Adds delimiters and merges songs into one text file. Creates parent directories if needed."""
    # Ensure parent directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Delimiter length matches sequence length to prevent cross-song learning
    delimiter = " / " * sequence_length
    dataset = ""
    for song in songs:
        dataset += song + delimiter
    
    # Open in "w" mode to overwrite existing files
    with open(output_path, "w") as f:
        f.write(dataset.strip())
    return dataset

def create_mapping(dataset, mapping_path):
    """Creates a JSON lookup table for symbols. Creates parent directories if needed."""
    # Ensure parent directory exists
    mapping_dir = os.path.dirname(mapping_path)
    if mapping_dir and not os.path.exists(mapping_dir):
        os.makedirs(mapping_dir)
    
    vocab = list(set(dataset.split()))
    mapping = {symbol: i for i, symbol in enumerate(vocab)}
    
    # Open in "w" mode to overwrite existing files
    with open(mapping_path, "w") as f:
        json.dump(mapping, f, indent=4)
    return mapping

def generate_training_sequences(dataset, mapping, sequence_length):
    """Generates sliding window sequences and one-hot encodes inputs."""
    int_songs = [mapping[symbol] for symbol in dataset.split()]
    
    inputs, targets = [], []
    num_sequences = len(int_songs) - sequence_length
    
    for i in range(num_sequences):
        inputs.append(int_songs[i:i+sequence_length])
        targets.append(int_songs[i+sequence_length])
        
    vocab_size = len(mapping)
    # One-hot encoding is necessary for categorical musical symbols
    inputs = keras.utils.to_categorical(inputs, num_classes=vocab_size)
    targets = np.array(targets)
    
    return inputs, targets

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Preprocess MIDI files from a custom directory and generate training datasets."
    )
    parser.add_argument(
        "--midi-dir",
        type=str,
        default="chopin",
        help="Path to directory containing MIDI files (default: %(default)s). Supports absolute paths."
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default="file_dataset.txt",
        help="Output path for the dataset file (default: %(default)s). Supports absolute paths."
    )
    parser.add_argument(
        "--mapping-path",
        type=str,
        default="mapping.json",
        help="Output path for the mapping file (default: %(default)s). Supports absolute paths."
    )
    
    args = parser.parse_args()
    
    # Verify MIDI directory exists
    if not os.path.exists(args.midi_dir):
        print(f"Error: MIDI directory '{args.midi_dir}' does not exist.")
        exit(1)
    
    processed_songs = preprocess(args.midi_dir)
    full_dataset = create_single_file_dataset(processed_songs, args.dataset_path, SEQUENCE_LENGTH)
    symbol_mapping = create_mapping(full_dataset, args.mapping_path)
    X, y = generate_training_sequences(full_dataset, symbol_mapping, SEQUENCE_LENGTH)
    
    print(f"Preprocessing Complete.")
    print(f"  Dataset saved to: {os.path.abspath(args.dataset_path)}")
    print(f"  Mapping saved to: {os.path.abspath(args.mapping_path)}")
    print(f"  X shape: {X.shape}, y shape: {y.shape}")