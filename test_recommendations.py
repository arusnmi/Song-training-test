"""
Test Script for Recommendation Engine
Tests collaborative filtering, content-based filtering, and Gemini integration
"""

import os
from recommendation_engine import RecommendationEngine, GeminiExplainer

def main():
    # Paths
    capstone_dir = r"c:\Users\warty\OneDrive\Desktop\Python_projects\Capstone_music_maker\Scenario 2_ AI Music Composer & Listener Insight platform"
    music_info = os.path.join(capstone_dir, "Music Info.csv")
    listening_history = os.path.join(capstone_dir, "User Listening History.csv")
    
    print("=" * 80)
    print("SoniqueAI - Recommendation Engine Test")
    print("=" * 80)
    
    # Initialize engine
    print("\n📥 Loading recommendation engine...")
    rec_engine = RecommendationEngine(music_info, listening_history)
    print("✅ Engine loaded successfully!")
    
    # Initialize Gemini
    print("\n🤖 Initializing Gemini explainer...")
    gemini = GeminiExplainer(api_key=None)  # Set API key if available
    print("✅ Gemini ready (explanations will use defaults)")
    
    # Get sample users
    all_users = rec_engine.get_all_user_ids()
    print(f"\n👥 Total users in dataset: {len(all_users)}")
    
    # Test with first user
    test_user = all_users[0]
    print(f"\n🧪 Testing with user: {test_user}")
    
    # Get user preferences
    print("\n📊 User Preferences:")
    prefs = rec_engine.get_user_preferences(test_user)
    if prefs:
        print(f"  - Songs listened: {prefs['total_songs_listened']}")
        print(f"  - Avg energy: {prefs['avg_energy']:.2f}")
        print(f"  - Avg valence: {prefs['avg_valence']:.2f}")
        print(f"  - Avg danceability: {prefs['avg_danceability']:.2f}")
        print(f"  - Avg acousticness: {prefs['avg_acousticness']:.2f}")
    
    # Test Collaborative Filtering
    print(f"\n1️⃣ Collaborative Filtering Recommendations:")
    collab_recs = rec_engine.collaborative_filtering(test_user, top_n=5)
    for i, rec in enumerate(collab_recs, 1):
        print(f"  {i}. {rec['name']} - {rec['artist']}")
        print(f"     Genre: {rec['genre']} | Energy: {rec['energy']:.2f}")
    
    # Test Content-Based Filtering
    print(f"\n2️⃣ Content-Based Filtering Recommendations:")
    content_recs = rec_engine.content_based_filtering(test_user, top_n=5)
    for i, rec in enumerate(content_recs, 1):
        print(f"  {i}. {rec['name']} - {rec['artist']}")
        print(f"     Genre: {rec['genre']} | Valence: {rec['valence']:.2f}")
    
    # Test Hybrid
    print(f"\n3️⃣ Hybrid Recommendations:")
    hybrid_recs = rec_engine.hybrid_recommendations(test_user, top_n=5)
    for i, rec in enumerate(hybrid_recs, 1):
        print(f"  {i}. {rec['name']} - {rec['artist']} ({rec['method']})")
        
        # Generate explanation
        explanation = gemini.generate_explanation(rec, prefs)
        print(f"     💡 {explanation}")
    
    # Test song search
    print(f"\n🔍 Song Search Test:")
    print("Searching for 'Coldplay'...")
    results = rec_engine.get_song_by_name("Coldplay")
    if not results.empty:
        for idx, song in results.head(3).iterrows():
            print(f"  - {song['name']} by {song['artist']}")
    
    print("\n" + "=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)

if __name__ == "__main__":
    main()
