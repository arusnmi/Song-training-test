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
from pathlib import Path
from collections import Counter
import re

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

@st.cache_data
def load_midi_tracks():
    """Return available MIDI song names from the local Midi_files folder."""
    script_dir = Path(__file__).resolve().parent
    cwd_dir = Path.cwd().resolve()

    midi_candidates = [
        script_dir / "Midi_files",
        cwd_dir / "Midi_files",
    ]

    midi_dir = next((p for p in midi_candidates if p.exists() and p.is_dir()), None)
    if midi_dir is None:
        return []

    midi_files = []
    for pattern in ("*.mid", "*.midi"):
        midi_files.extend(midi_dir.glob(pattern))

    return sorted({midi_file.name for midi_file in midi_files})

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

# Initialize engines
load_error = None
try:
    rec_engine = load_recommendation_engine()
except Exception as e:
    rec_engine = None
    load_error = str(e)

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

# derive feedback from the listening history CSV
sample_feedback = load_feedback_from_history(rec_engine)

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

    # use track names from the loaded recommendation engine (falls back to empty list)
    if rec_engine is not None and hasattr(rec_engine, 'music_df'):
        # take first 100 names for performance in UI
        dataset = rec_engine.music_df['name'].dropna().unique().tolist()[:100]
    else:
        dataset = []

    midi_dataset = load_midi_tracks()

    # COMPOSE
    if mode == "Compose (AI Generated)":

        st.write("Generate music using a random seed from dataset")

        if not dataset:
            st.info("⚠️ No track data available. Ensure the CSVs are present in the repository root.")
        else:
            if st.button("Generate Composition"):
                seed_song = random.choice(dataset)
                st.success(f"Seed song selected: {seed_song}")
                st.audio(
                    "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav"
                )

    # REMIX
    if mode == "Remix Songs":

        if not midi_dataset:
            st.info("⚠️ No MIDI songs found in the Midi_files folder.")
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
                    st.success(f"Remixed {track1} and {track2}")
                    st.audio(
                        "https://www.soundjay.com/misc/sounds/bell-ringing-05.wav"
                    )

# -----------------------------
# RECOMMENDATIONS
# -----------------------------
elif page == "Recommendations":

    st.header("🎧 Music Recommendations Engine")

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


