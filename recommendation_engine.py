"""
Comprehensive Recommendation Engine
Includes: Collaborative Filtering, Content-Based Filtering, and Gemini Integration
"""

import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class RecommendationEngine:
    def __init__(self, music_info_path, listening_history_path):
        """
        Initialize the recommendation engine
        
        Args:
            music_info_path: Path to Music Info CSV
            listening_history_path: Path to User Listening History CSV
        """
        self.music_df = pd.read_csv(music_info_path)
        self.listening_df = self._load_listening_history(listening_history_path)
        self.user_item_matrix = None
        self.song_features_matrix = None
        self.build_matrices()
        
    def _load_listening_history(self, path, sample_size=100000):
        """Load listening history with memory optimization"""
        print(f"Loading listening history (sampling {sample_size} rows for performance)...")
        df = pd.read_csv(path, nrows=sample_size)
        return df
    
    def build_matrices(self):
        """Build user-item matrix and feature matrix"""
        print("Building matrices...")
        
        # Create user-item matrix (rows=users, cols=songs, values=playcount)
        self.user_item_matrix = self.listening_df.pivot_table(
            index='user_id',
            columns='track_id',
            values='playcount',
            fill_value=0
        )
        print(f"User-Item Matrix shape: {self.user_item_matrix.shape}")
        
        # Build song feature matrix from audio features
        feature_cols = [
            'danceability', 'energy', 'key', 'loudness', 'mode',
            'speechiness', 'acousticness', 'instrumentalness',
            'liveness', 'valence', 'tempo'
        ]
        
        available_features = [col for col in feature_cols if col in self.music_df.columns]

        if not available_features:
            # Keep content-based pipeline alive even if feature columns are absent.
            self.song_features_matrix = pd.DataFrame(
                0.0,
                index=self.user_item_matrix.columns,
                columns=['fallback_feature']
            )
        else:
            # Create feature matrix, aligned with user_item_matrix columns (track_ids).
            feature_data = self.music_df.set_index('track_id')[available_features].fillna(0)

            # Use reindex instead of loc so missing track_ids are filled with zeros
            # instead of raising KeyError when listening history has extra tracks.
            self.song_features_matrix = feature_data.reindex(self.user_item_matrix.columns).fillna(0)

        # Normalize features
        scaler = StandardScaler()
        self.song_features_normalized = scaler.fit_transform(self.song_features_matrix)
        
        print(f"Song Features Matrix shape: {self.song_features_matrix.shape}")
    
    def collaborative_filtering(self, user_id, top_n=5):
        """
        Recommend songs using collaborative filtering
        Find similar users and recommend songs they liked
        """
        if user_id not in self.user_item_matrix.index:
            return []
        
        # Get user's listening profile
        user_profile = self.user_item_matrix.loc[user_id].values.reshape(1, -1)
        
        # Calculate similarity with all users
        similarities = cosine_similarity(user_profile, self.user_item_matrix.values)[0]
        
        # Find most similar users (excluding the user itself)
        similar_user_indices = np.argsort(-similarities)[1:6]  # Top 5 similar users
        similar_users = self.user_item_matrix.index[similar_user_indices]
        
        # Aggregate songs from similar users
        recommendations = {}
        user_songs = set(self.user_item_matrix.loc[user_id][self.user_item_matrix.loc[user_id] > 0].index)
        
        for sim_user in similar_users:
            sim_user_songs = self.user_item_matrix.loc[sim_user]
            for track_id, playcount in sim_user_songs[sim_user_songs > 0].items():
                if track_id not in user_songs:
                    recommendations[track_id] = recommendations.get(track_id, 0) + playcount
        
        # Sort and return top N
        sorted_recs = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)[:top_n]
        track_ids = [rec[0] for rec in sorted_recs]
        
        return self._enrich_recommendations(track_ids, 'collaborative')
    
    def content_based_filtering(self, user_id, top_n=5):
        """
        Recommend songs using content-based filtering
        Find songs similar to what the user has already liked
        """
        if user_id not in self.user_item_matrix.index:
            return []
        
        # Get user's liked songs
        user_songs = self.user_item_matrix.loc[user_id]
        liked_song_indices = np.where(user_songs > 0)[0]
        
        if len(liked_song_indices) == 0:
            return []
        
        # Calculate average feature profile of liked songs
        user_feature_profile = self.song_features_normalized[liked_song_indices].mean(axis=0).reshape(1, -1)
        
        # Find similarity with all songs
        similarities = cosine_similarity(user_feature_profile, self.song_features_normalized)[0]
        
        # Get songs user hasn't listened to
        unheard_songs = np.where(user_songs == 0)[0]
        
        if len(unheard_songs) == 0:
            return []
        
        # Get top N similar songs from unheard
        top_indices = unheard_songs[np.argsort(-similarities[unheard_songs])[:top_n]]
        track_ids = self.user_item_matrix.columns[top_indices].tolist()
        
        return self._enrich_recommendations(track_ids, 'content-based')
    
    def hybrid_recommendations(self, user_id, top_n=5):
        """
        Combine collaborative and content-based filtering
        """
        collab_recs = self.collaborative_filtering(user_id, top_n=3)
        content_recs = self.content_based_filtering(user_id, top_n=3)
        
        # Merge and deduplicate
        all_recs = {rec['track_id']: rec for rec in collab_recs + content_recs}
        
        # Sort by combining scores
        sorted_recs = sorted(
            all_recs.values(),
            key=lambda x: x.get('score', 0),
            reverse=True
        )[:top_n]
        
        return sorted_recs
    
    def _enrich_recommendations(self, track_ids, method):
        """Enrich recommendations with song metadata"""
        recommendations = []
        
        for track_id in track_ids:
            song_info = self.music_df[self.music_df['track_id'] == track_id]
            
            if not song_info.empty:
                song = song_info.iloc[0]
                recommendations.append({
                    'track_id': track_id,
                    'name': song.get('name', 'Unknown'),
                    'artist': song.get('artist', 'Unknown'),
                    'genre': song.get('genre', 'Unknown'),
                    'energy': song.get('energy', 0),
                    'valence': song.get('valence', 0),
                    'danceability': song.get('danceability', 0),
                    'acousticness': song.get('acousticness', 0),
                    'instrumentalness': song.get('instrumentalness', 0),
                    'method': method,
                    'score': len(track_ids) - len(recommendations)  # Simple scoring
                })
        
        return recommendations
    
    def get_user_preferences(self, user_id):
        """Get user's music preferences from listening history"""
        if user_id not in self.user_item_matrix.index:
            return None
        
        # Get songs the user has listened to
        user_songs = self.user_item_matrix.loc[user_id]
        listened_track_ids = user_songs[user_songs > 0].index.tolist()
        
        if len(listened_track_ids) == 0:
            return None
        
        # Get metadata for listened songs
        liked_songs = self.music_df[self.music_df['track_id'].isin(listened_track_ids)]
        
        preferences = {
            'favorite_genres': liked_songs['genre'].value_counts().head(5).to_dict() if 'genre' in liked_songs.columns else {},
            'avg_energy': liked_songs['energy'].mean() if 'energy' in liked_songs.columns else 0,
            'avg_valence': liked_songs['valence'].mean() if 'valence' in liked_songs.columns else 0,
            'avg_danceability': liked_songs['danceability'].mean() if 'danceability' in liked_songs.columns else 0,
            'avg_acousticness': liked_songs['acousticness'].mean() if 'acousticness' in liked_songs.columns else 0,
            'total_songs_listened': len(listened_track_ids)
        }
        
        return preferences
    
    def get_all_user_ids(self):
        """Get list of all user IDs"""
        return self.user_item_matrix.index.tolist()
    
    def get_song_by_name(self, query):
        """Search for songs by name"""
        results = self.music_df[
            self.music_df['name'].str.contains(query, case=False, na=False)
        ].head(10)
        return results


class GeminiExplainer:
    """Generate explanations for recommendations using Gemini API"""
    
    def __init__(self, api_key=None):
        """Initialize Gemini client"""
        self.api_key = api_key
        self.client = None
        
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.client = genai.GenerativeModel('gemini-pro')
            except Exception as e:
                print(f"Gemini API not available: {e}")
    
    def generate_explanation(self, recommendation, user_preferences=None):
        """Generate human-readable explanation for a recommendation"""
        
        if not self.client:
            return self._default_explanation(recommendation)
        
        try:
            prompt = f"""
            Explain why this song is recommended for a user in 1-2 sentences:
            
            Song: {recommendation['name']} by {recommendation['artist']}
            Genre: {recommendation['genre']}
            Energy: {recommendation['energy']:.2f}
            Valence (happiness): {recommendation['valence']:.2f}
            Danceability: {recommendation['danceability']:.2f}
            
            Recommendation method: {recommendation['method']}
            """
            
            if user_preferences:
                prompt += f"""
                User typically listens to songs with:
                - Average energy: {user_preferences.get('avg_energy', 0):.2f}
                - Average valence: {user_preferences.get('avg_valence', 0):.2f}
                - Average danceability: {user_preferences.get('avg_danceability', 0):.2f}
                """
            
            response = self.client.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error generating explanation: {e}")
            return self._default_explanation(recommendation)
    
    def _default_explanation(self, recommendation):
        """Generate default explanation without API"""
        method = recommendation['method']
        name = recommendation['name']
        artist = recommendation['artist']
        
        if method == 'collaborative':
            return f"Users like you also enjoyed '{name}' by {artist}."
        elif method == 'content-based':
            features = []
            if recommendation['energy'] > 0.7:
                features.append("energetic")
            if recommendation['valence'] > 0.7:
                features.append("uplifting")
            if recommendation['danceability'] > 0.7:
                features.append("danceable")
            
            feature_text = " and ".join(features) if features else "with similar characteristics"
            return f"Recommended because it's {feature_text}, matching your taste."
        else:
            return f"Recommended: '{name}' by {artist}"
