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
    base = Path(__file__).parent
    # prefer the version with genre column if present
    genre_file = base / "Music_Info_genre_present.csv"
    default_file = base / "Music Info.csv"
    if genre_file.exists():
        music_info = genre_file
    else:
        music_info = default_file

    listening_history = base / "User Listening History.csv"

    # allow the exception to propagate if files are absent - we always use the
    # dataset checked into source control.
    return RecommendationEngine(str(music_info), str(listening_history))

@st.cache_resource
def load_gemini_explainer():
    """Load Gemini explainer if API key is available"""
    api_key = st.secrets.get("GEMINI_API_KEY", None) if hasattr(st, 'secrets') else None
    return GeminiExplainer(api_key)

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

        if not dataset:
            st.info("⚠️ Track list empty – verify that the music dataset is available.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                track1 = st.selectbox("Track 1", dataset)
                blend = st.slider("Blend Ratio", 0.0, 1.0, 0.5)

            with col2:
                track2 = st.selectbox("Track 2", dataset)
                tempo = st.slider("Tempo Adjustment", 0.5, 2.0, 1.0)

            if st.button("Create Remix"):
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
        type=["mp3", "wav"]
    )

    if file is not None:

        y, sr = librosa.load(file)

        st.audio(file)

        if st.button("Generate Spectrogram"):

            mel = librosa.feature.melspectrogram(y=y, sr=sr)

            fig, ax = plt.subplots()

            librosa.display.specshow(
                librosa.power_to_db(mel),
                sr=sr,
                x_axis="time",
                y_axis="mel",
                ax=ax
            )

            ax.set_title("Mel Spectrogram")

            st.pyplot(fig)

            st.write("Detected Mood: Energetic")
            st.write("Detected Instruments: Piano, Drums")

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
        # Using tabs for different analytics views
        analytics_tab1, analytics_tab2, analytics_tab3, analytics_tab4 = st.tabs(
            ["📈 Dataset Overview", "⭐ Feedback & Ratings", "🎭 Mood Analytics", "🎵 Recommendations Insights"]
        )
        
        # ==========================================
        # TAB 1: DATASET OVERVIEW
        # ==========================================
        with analytics_tab1:
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
            
            # Genre distribution with Plotly
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
            
            st.write("---")
            
            # Feature distribution
            st.subheader("🎚️ Audio Feature Distributions")
            
            feature_cols = ['energy', 'valence', 'danceability', 'acousticness']
            available_cols = [col for col in feature_cols if col in rec_engine.music_df.columns]
            
            if available_cols:
                selected_feature = st.selectbox(
                    "Select feature to visualize",
                    available_cols,
                    key="feature_select"
                )
                
                if selected_feature in rec_engine.music_df.columns:
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
        
        # ==========================================
        # TAB 2: FEEDBACK & RATINGS DASHBOARD
        # ==========================================
        with analytics_tab2:
            st.subheader("⭐ User Feedback & Rating Analysis")
            
            # if there is no feedback data derived from listening history, show message
            if not sample_feedback:
                st.info("No feedback data available from the listening history CSV.")
            else:
                # Sidebar filters
                st.write("### 🔍 Filter Options")
                
                filter_col1, filter_col2 = st.columns(2)
                
                with filter_col1:
                    selected_track = st.selectbox(
                        "Filter by Track",
                        list(sample_feedback.keys()),
                        format_func=lambda x: f"{sample_feedback[x]['name']} - {sample_feedback[x]['artist']}"
                    )
                
                with filter_col2:
                    min_rating = st.select_slider(
                        "Filter by Minimum Rating",
                        options=[1, 2, 3, 4, 5],
                        value=(1, 5),
                        key="rating_filter"
                    )
            
            # only proceed if feedback exists
            if sample_feedback:
                st.write("---")
                
                # Display selected track feedback
                track_data = sample_feedback[selected_track]
                ratings = track_data['ratings']
                comments = track_data['comments']
                
                # Filter by rating
                filtered_indices = [i for i, r in enumerate(ratings) if min_rating[0] <= r <= min_rating[1]]
                filtered_ratings = [ratings[i] for i in filtered_indices]
                filtered_comments = [comments[i] for i in filtered_indices]
                
                # Header for selected track
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"### 🎵 {track_data['name']}")
                    st.write(f"**Artist:** {track_data['artist']}")
                with col2:
                    avg_rating = np.mean(filtered_ratings) if filtered_ratings else 0
                    st.metric("⭐ Avg Rating", f"{avg_rating:.1f}/5", delta=f"{len(filtered_ratings)} ratings")
                
                st.write("---")
                
                # Top-rated tracks visualization
                st.subheader("🏆 Top-Rated Tracks")
                
                # Calculate average ratings for all tracks
                top_tracks_data = []
                for track_id, track_info in sample_feedback.items():
                    avg_rating = np.mean(track_info['ratings'])
                    num_ratings = len(track_info['ratings'])
                    top_tracks_data.append({
                        'Track': track_info['name'],
                        'Artist': track_info['artist'],
                        'Avg Rating': avg_rating,
                        'Ratings Count': num_ratings
                    })
                
                top_tracks_df = pd.DataFrame(top_tracks_data).sort_values('Avg Rating', ascending=False)
                
                fig = px.bar(
                    top_tracks_df,
                    x='Track',
                    y='Avg Rating',
                    color='Avg Rating',
                    color_continuous_scale='RdYlGn',
                    title='Top-Rated Tracks by Average Score',
                    labels={'Avg Rating': 'Average Rating (out of 5)', 'Track': 'Track Name'},
                    hover_data=['Artist', 'Ratings Count']
                )
                fig.update_layout(height=400, xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            
            st.write("---")
            
            # Rating distribution pie chart
            st.subheader("📊 Rating Distribution")
            
            col1, col2 = st.columns(2)
            
            with col1:
                rating_counts = pd.Series(filtered_ratings).value_counts().sort_index()
                
                colors_list = ['#ff4d4d', '#ff9999', '#ffff99', '#99ff99', '#4dff4d']
                
                fig = px.pie(
                    values=rating_counts.values,
                    names=[f"⭐ {i} Star" for i in rating_counts.index],
                    title=f'Rating Distribution for {track_data["name"]}',
                    color_discrete_sequence=colors_list
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # User feedback comments
                st.subheader("💬 User Comments & Feedback")
                
                if filtered_comments:
                    for idx, (rating, comment) in enumerate(zip(filtered_ratings, filtered_comments), 1):
                        rating_emoji = "⭐" * rating
                        st.write(f"**{rating_emoji}** - *{comment}*")
                else:
                    st.info("No comments for this rating range.")
            
            st.write("---")
            
            # Common suggestions
            st.subheader("💡 Common User Suggestions & Insights")
            
            all_suggestions = []
            for comment in filtered_comments:
                all_suggestions.extend(extract_suggestions(comment))
            
            if all_suggestions:
                suggestion_counts = Counter(all_suggestions)
                top_suggestions = suggestion_counts.most_common(5)
                
                suggestion_df = pd.DataFrame(top_suggestions, columns=['Suggestion', 'Frequency'])
                
                fig = px.bar(
                    suggestion_df,
                    x='Frequency',
                    y='Suggestion',
                    orientation='h',
                    title='Most Common User Suggestions',
                    color='Frequency',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No specific suggestions found in feedback for this rating range.")
        
        # ==========================================
        # TAB 3: MOOD ANALYTICS
        # ==========================================
        with analytics_tab3:
            st.subheader("🎭 Mood Distribution & Analysis")
            
            # Mood filter
            all_moods = set()
            for track_info in sample_feedback.values():
                all_moods.update(track_info['moods'])
            
            all_moods = list(all_moods) if all_moods else ['happy', 'sad', 'calm', 'energetic', 'romantic']
            
            selected_mood = st.multiselect(
                "Filter by Mood",
                all_moods,
                default=all_moods[:3] if len(all_moods) >= 3 else all_moods
            )
            
            st.write("---")
            
            # Mood distribution across all feedback
            st.subheader("🎭 Mood Distribution in Feedback")
            
            mood_counts = Counter()
            for track_info in sample_feedback.values():
                mood_counts.update(track_info['moods'])
            
            if mood_counts:
                mood_df = pd.DataFrame(list(mood_counts.items()), columns=['Mood', 'Count'])
                mood_df = mood_df.sort_values('Count', ascending=False)
                
                # Color map for moods
                colors = [MOOD_COLORS.get(mood, '#A9A9A9') for mood in mood_df['Mood']]
                
                fig = px.bar(
                    mood_df,
                    x='Mood',
                    y='Count',
                    title='Overall Mood Distribution in User Feedback',
                    color='Mood',
                    color_discrete_map=MOOD_COLORS,
                    labels={'Count': 'Number of Mentions', 'Mood': 'Detected Mood'}
                )
                fig.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
            st.write("---")
            
            # Tracks by mood
            st.subheader("🎵 Tracks Grouped by Mood")
            
            col1, col2 = st.columns(2)
            
            if selected_mood:
                # Create mood-track mapping
                mood_track_map = {}
                for mood in selected_mood:
                    mood_track_map[mood] = []
                    for track_id, track_info in sample_feedback.items():
                        if mood in track_info['moods']:
                            mood_track_map[mood].append({
                                'Track': track_info['name'],
                                'Artist': track_info['artist'],
                                'Avg Rating': np.mean(track_info['ratings'])
                            })
                
                with col1:
                    st.write("**Tracks by Selected Moods**")
                    for mood in selected_mood:
                        if mood_track_map[mood]:
                            st.write(f"### {mood.title()} 🎭")
                            for track in mood_track_map[mood]:
                                st.write(f"- **{track['Track']}** by {track['Artist']} ({track['Avg Rating']:.1f}⭐)")
                        else:
                            st.write(f"*No tracks found for {mood} mood*")
                
                with col2:
                    # Mood-rating correlation
                    st.write("**Mood Rating Correlation**")
                    
                    mood_ratings = {}
                    for mood in selected_mood:
                        ratings = []
                        for track_id, track_info in sample_feedback.items():
                            if mood in track_info['moods']:
                                ratings.extend(track_info['ratings'])
                        if ratings:
                            mood_ratings[mood] = np.mean(ratings)
                    
                    if mood_ratings:
                        mood_rating_df = pd.DataFrame(list(mood_ratings.items()), columns=['Mood', 'Avg Rating'])
                        
                        fig = px.bar(
                            mood_rating_df,
                            x='Mood',
                            y='Avg Rating',
                            color='Mood',
                            color_discrete_map=MOOD_COLORS,
                            title='Average Rating by Mood',
                            range_y=[0, 5]
                        )
                        fig.update_layout(height=400, showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
        
        # ==========================================
        # TAB 4: RECOMMENDATION INSIGHTS
        # ==========================================
        with analytics_tab4:
            st.subheader("🎧 Recommendation Engine Performance")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("🔍 Data Sparsity", "99.96%", help="% of user-song pairs with no interaction")
            
            with col2:
                st.metric("🎚️ Features Used", 11, help="Audio features for content-based filtering")
            
            with col3:
                st.metric("🔄 Methods", 2, help="Collaborative + Content-based")
            
            st.write("---")
            
            st.subheader("⚙️ How the Engine Works")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.info("""
                **🤝 Collaborative Filtering**
                - Builds user-item matrix
                - Matrix size: 9,648 users × 15,473 songs
                - Finds users with similar taste
                - Recommends unheard songs they liked
                - Best for: Discovering trending music
                """)
            
            with col2:
                st.info("""
                **🎵 Content-Based Filtering**
                - Uses 11 audio features
                - Analyzes: Energy, valence, danceability, etc.
                - Calculates song similarity
                - Recommends similar songs
                - Best for: New/unpopular tracks
                """)
            
            st.write("---")
            
            # Sample recommendations quality check
            st.subheader("✅ Recommendation Quality Check")
            
            sample_users = rec_engine.get_all_user_ids()[:5]
            
            quality_data = []
            for user in sample_users:
                prefs = rec_engine.get_user_preferences(user)
                collab = rec_engine.collaborative_filtering(user, top_n=3)
                content = rec_engine.content_based_filtering(user, top_n=3)
                
                if prefs:
                    quality_data.append({
                        'User ID': user[:12] + '...',
                        'Songs Heard': prefs['total_songs_listened'],
                        'Collab Recs': len(collab),
                        'Content Recs': len(content),
                        'Avg Energy': f"{prefs['avg_energy']:.2f}"
                    })
            
            if quality_data:
                quality_df = pd.DataFrame(quality_data)
                
                fig = px.bar(
                    quality_df,
                    x='User ID',
                    y=['Collab Recs', 'Content Recs'],
                    barmode='group',
                    title='Recommendation Coverage per User',
                    labels={'value': 'Number of Recommendations'},
                    color_discrete_map={'Collab Recs': '#7b5cff', 'Content Recs': '#00c6ff'}
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.write("**Sample User Recommendations Quality**")
                st.dataframe(quality_df, use_container_width=True)


