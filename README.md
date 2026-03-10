# 🎧 SoniqueAI - AI Music Creation & Recommendation Platform

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.0+-red)
![Machine Learning](https://img.shields.io/badge/ML-Scikit--Learn-orange)

## Overview

SoniqueAI is a comprehensive AI-powered music platform featuring:

- **🎵 Hybrid Recommendation Engine** - Collaborative + Content-Based Filtering
- **🎭 Mood & Instrument Analysis** - Real-time audio analysis
- **🎼 AI Music Generation** - Generate and remix songs
- **📊 Advanced Analytics** - Visualize music trends and features
- **🤖 Gemini AI Integration** - Personalized explanations
- **💾 User Preference Tracking** - Learn from listening history

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test the Recommendation Engine
```bash
python test_recommendations.py
```

### 3. Run the Application
```bash
streamlit run streamlit_app.py
```

The app will open at `http://localhost:8501`

## Features

### 🎵 Hybrid Recommendation Engine

#### Collaborative Filtering
Finds users with similar listening patterns and recommends their favorite songs.

#### Content-Based Filtering
Recommends songs similar to what you've liked, based on 11 audio features:
- Energy, Valence, Danceability, Acousticness, Instrumentalness, Tempo, Loudness, Speechiness, Key, Mode, Liveness

#### Hybrid Approach
Combines both methods (50/50 weight) for optimal recommendations.

### 📊 Analytics Dashboard

- **Dataset Overview**: 9,648 users, 15,473 songs, 1M+ interactions
- **Genre Analysis**: Distribution and trends
- **Feature Analysis**: Correlation matrices and distributions
- **Recommendation Metrics**: Engine performance and quality

### 🎭 Mood & Instrument Analyzer
- Upload MP3/WAV files
- Generate mel-spectrograms
- Analyze mood and instruments in real-time

### 🎼 Remix / Compose Studio
- Generate AI music
- Remix multiple tracks
- Control tempo and blend ratios

## Data Requirements

Place these files in: `Capstone_music_maker/Scenario 2_ AI Music Composer & Listener Insight platform/`

- **Music Info.csv** (~50MB) - Song metadata and audio features
- **User Listening History.csv** (~600MB) - User-song listening counts

## Configuration

### Optional: Gemini API Integration

1. Get free API key: https://makersuite.google.com/app/apikey
2. Create `.streamlit/secrets.toml`:
```toml
GEMINI_API_KEY = "your-api-key-here"
```
3. Restart Streamlit

Without API key, the system uses intelligent default explanations.

### Customize Settings

Edit `config.py` to adjust:
- Sample size (for performance vs accuracy)
- Number of recommendations
- Similar users to analyze
- Feature weights
- And more...

## File Structure

```
Song-training-test/
├── streamlit_app.py             # Main UI application
├── recommendation_engine.py     # ML algorithms
├── config.py                    # Settings & configuration
├── test_recommendations.py      # Engine tests
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── SETUP_GUIDE.md              # Detailed setup instructions
├── RECOMMENDATION_GUIDE.md     # Technical documentation
└── .streamlit/
    ├── config.toml             # Streamlit settings
    └── secrets.toml            # API keys (git-ignored)
```

## How It Works

### Collaborative Filtering
1. Builds a user-item matrix (users × songs, values = playcount)
2. Finds users with similar listening patterns
3. Recommends unheard songs from similar users

### Content-Based Filtering
1. Analyzes audio features of songs you like
2. Calculates similarity with all other songs
3. Recommends most similar unheard songs

### Hybrid Approach
- 3 recommendations from collaborative filtering
- 3 recommendations from content-based filtering
- Deduplicates and ranks by relevance

## Performance

| Metric | Value |
|--------|-------|
| Users | 9,648 |
| Songs | 15,473 |
| Data Sparsity | 99.96% |
| Init Time | 5-10s |
| Per Recommendation | 0.5-1s |

## Example Code

```python
from recommendation_engine import RecommendationEngine, GeminiExplainer

# Initialize
engine = RecommendationEngine(
    "Music Info.csv",
    "User Listening History.csv"
)

# Get recommendations
user_id = "user_hash_here"
recommendations = engine.hybrid_recommendations(user_id, top_n=5)

# Add explanations
explainer = GeminiExplainer(api_key="your-key")
for rec in recommendations:
    explanation = explainer.generate_explanation(rec)
    print(f"{rec['name']} - {rec['artist']}")
    print(f"Why: {explanation}\n")
```

## Troubleshooting

### Missing CSV files
Check file paths in `config.py`. Ensure CSV files exist at specified locations.

### Slow recommendations
Reduce `LISTENING_HISTORY_SAMPLE_SIZE` in `config.py` (default: 100,000).

### Gemini API errors
- Verify API key is valid
- Check internet connection
- Remove `secrets.toml` to use defaults

### No recommendations found
Some users may not have similar users or unheard songs. Try different user IDs.

### Import errors
```bash
pip install scikit-learn pandas numpy matplotlib librosa streamlit
```

## Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Installation and deployment
- **[RECOMMENDATION_GUIDE.md](RECOMMENDATION_GUIDE.md)** - Technical details

## Architecture

```
Streamlit UI
    ↓
Recommendation Engine
    ├─ Collaborative Filtering (User-Item Matrix)
    ├─ Content-Based Filtering (Feature Similarity)
    └─ Hybrid Combining
         ↓
    Data Processing
    ├─ Cosine Similarity
    ├─ Feature Normalization
    └─ Ranking
```

## Deployment

### Streamlit Cloud
1. Push to GitHub
2. Connect at streamlit.io
3. Set `GEMINI_API_KEY` in secrets

### Docker
```bash
docker build -t soniqueai .
docker run -p 8501:8501 soniqueai
```

## Future Enhancements

- [ ] Matrix factorization (SVD, NMF)
- [ ] Deep learning models
- [ ] Real-time streaming
- [ ] Cold-start solutions
- [ ] Explainability (SHAP)
- [ ] A/B testing framework

## License

MIT License - Feel free to use and modify!

## Support

For detailed information:
- See [SETUP_GUIDE.md](SETUP_GUIDE.md) for installation
- See [RECOMMENDATION_GUIDE.md](RECOMMENDATION_GUIDE.md) for technical details
- Run `python test_recommendations.py` to test the engine

---

**🎵 Enjoy discovering music with AI! 🤖**