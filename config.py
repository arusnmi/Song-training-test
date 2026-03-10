"""
Configuration module for SoniqueAI
Manages data paths, settings, and environment variables
"""

import os
from pathlib import Path

# ========================
# Data Paths
# ========================

# Base directories
CAPSTONE_DIR = Path(
    r"c:\Users\warty\OneDrive\Desktop\Python_projects\Capstone_music_maker"
    r"\Scenario 2_ AI Music Composer & Listener Insight platform"
)

SONG_TRAINING_DIR = Path(
    r"c:\Users\warty\OneDrive\Desktop\Python_projects\Song-training-test"
)

# Data files
MUSIC_INFO_CSV = CAPSTONE_DIR / "Music Info.csv"
LISTENING_HISTORY_CSV = CAPSTONE_DIR / "User Listening History.csv"
MUSIC_INFO_GENRE_CSV = CAPSTONE_DIR / "Music Info_genre_filled.csv"
MUSIC_INFO_LABELED_CSV = CAPSTONE_DIR / "Music Info_labeled.csv"

# Output directories
GENERATED_SONGS_DIR = SONG_TRAINING_DIR / "generated_songs"
MODEL_DATA_DIR = SONG_TRAINING_DIR / "model_data"

# ========================
# Recommendation Settings
# ========================

# Data loading
LISTENING_HISTORY_SAMPLE_SIZE = 100000  # Load first N records for performance
MIN_USER_LISTENS = 1  # Minimum listens to consider a user

# Collaborative Filtering
COLLAB_SIMILAR_USERS = 5  # Number of similar users to find
COLLAB_TOP_RECOMMENDATIONS = 5  # Top songs from similar users

# Content-Based Filtering
CONTENT_TOP_RECOMMENDATIONS = 5  # Top similar songs to recommend
CONTENT_SIMILARITY_THRESHOLD = 0.0  # Minimum similarity score

# Hybrid Filtering
HYBRID_COLLAB_RATIO = 0.5  # Weight for collaborative filtering
HYBRID_CONTENT_RATIO = 0.5  # Weight for content-based filtering

# Audio Features Used
AUDIO_FEATURES = [
    'danceability', 'energy', 'key', 'loudness', 'mode',
    'speechiness', 'acousticness', 'instrumentalness',
    'liveness', 'valence', 'tempo'
]

# ========================
# API Settings
# ========================

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", None)
USE_GEMINI = GEMINI_API_KEY is not None

# ========================
# Streamlit Settings
# ========================

STREAMLIT_THEME = "dark"
STREAMLIT_PAGE_ICON = "🎧"

# ========================
# Feature Normalization
# ========================

NORMALIZE_FEATURES = True
FEATURE_SCALER = "StandardScaler"  # Options: StandardScaler, MinMaxScaler

# ========================
# Validation
# ========================

def validate_paths():
    """Check if all required data files exist"""
    missing = []
    
    if not MUSIC_INFO_CSV.exists():
        missing.append(f"Music Info CSV: {MUSIC_INFO_CSV}")
    
    if not LISTENING_HISTORY_CSV.exists():
        missing.append(f"Listening History CSV: {LISTENING_HISTORY_CSV}")
    
    if missing:
        print("⚠️  Warning: Missing data files:")
        for file in missing:
            print(f"  - {file}")
        return False
    
    return True

def create_output_directories():
    """Create output directories if they don't exist"""
    GENERATED_SONGS_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ========================
# Logging Configuration
# ========================

LOGGING_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR

# ========================
# Performance Settings
# ========================

# Cache settings
CACHE_RECOMMENDATIONS = True
CACHE_TIMEOUT = 3600  # seconds (1 hour)

# Matrix operation settings
USE_SPARSE_MATRIX = True  # Use sparse matrix for efficiency
PARALLEL_PROCESSING = True
N_JOBS = -1  # Use all processors

# ========================
# Feature Engineering
# ========================

# Feature scaling parameters
FEATURE_MIN_MAX = {
    'danceability': (0, 1),
    'energy': (0, 1),
    'valence': (0, 1),
    'acousticness': (0, 1),
    'instrumentalness': (0, 1),
    'tempo': (0, 300),
    'loudness': (-60, 0),
}

# ========================
# Recommendation Output
# ========================

# Default recommendation display
DEFAULT_TOP_N = 5
MAX_TOP_N = 10

# Include metadata
INCLUDE_SONG_METADATA = True
INCLUDE_SIMILARITY_SCORE = True
INCLUDE_METHOD_NAME = True

# ========================
# Debug Settings
# ========================

DEBUG_MODE = False
VERBOSE_LOGGING = False

if __name__ == "__main__":
    print("🎧 SoniqueAI Configuration")
    print("=" * 50)
    print(f"Music Info CSV: {MUSIC_INFO_CSV.exists() and '✅' or '❌'}")
    print(f"Listening History CSV: {LISTENING_HISTORY_CSV.exists() and '✅' or '❌'}")
    print(f"Sample Size: {LISTENING_HISTORY_SAMPLE_SIZE}")
    print(f"Audio Features: {len(AUDIO_FEATURES)}")
    print(f"Gemini API Available: {USE_GEMINI and '✅' or '❌'}")
    print("=" * 50)
