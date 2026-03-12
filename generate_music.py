import os
from music_generation_core import (
    convert_to_midi,
    generate_song_with_model,
    load_generation_model,
    load_note_mappings,
)


def generate_song(model, note_to_int, int_to_note, seed_file_path_1, seed_file_path_2, num_notes, temperature):
    """Compatibility wrapper for existing call sites."""
    print("Generating notes...")
    return generate_song_with_model(
        model,
        note_to_int,
        int_to_note,
        seed_file_path_1,
        seed_file_path_2,
        num_notes,
        temperature,
    )

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

    # Load vocabulary
    n2i, i2n = load_note_mappings(n2i_file)

    print("Loading model from file (this may take a moment)...")
    model, load_warning = load_generation_model(model_file)
    if model is None:
        print(f"ERROR: Failed to load model. {load_warning}")
        return
    if load_warning:
        print(f"Model compatibility warning: {load_warning}")

    out_folder = os.path.join(BASE, "generated_songs")
    os.makedirs(out_folder, exist_ok=True)

    # Path to your local MIDI seed
    seed_file_1 = os.path.join(BASE, "10cc_-_Dreadlock_Holiday.mid")
    seed_file_2 = os.path.join(BASE, "10cc_-_Im_Not_In_Love.mid")
    
    notes = generate_song(model, n2i, i2n, seed_file_1,seed_file_2, 400, 1)
    
    output_file = os.path.join(out_folder, "composition.mid")
    convert_to_midi(notes, output_file)
    print(f"\nSUCCESS! Saved to: {output_file}")




if __name__ == "__main__":
    run()