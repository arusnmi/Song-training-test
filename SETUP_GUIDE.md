# 🎧 SoniqueAI - Setup & Deployment Guide

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Test the Engine
```bash
python test_recommendations.py
```

### 3. Run Streamlit App
```bash
streamlit run streamlit_app.py
```

## Data Files Required

Place these files in: `c:\Users\warty\OneDrive\Desktop\Python_projects\Capstone_music_maker\Scenario 2_ AI Music Composer & Listener Insight platform\`

- **Music Info.csv** - Song metadata and audio features
- **User Listening History.csv** - User-song listen counts

## Features

### 🎵 Recommendations Page
- **Hybrid Filtering**: Combines collaborative + content-based filtering
- **Collaborative Filtering**: Finds users with similar taste
- **Content-Based Filtering**: Recommends similar songs
- **User Profile**: Shows your music preferences
- **Visualizations**: Energy, valence, danceability profiles
- **AI Explanations**: Why each song is recommended (with Gemini API)

### 📊 Analytics Dashboard
- **Dataset Overview**: Total users, songs, sparsity
- **Genre Distribution**: Which genres are in the dataset
- **Audio Features**: Energy, valence, danceability analysis
- **Feature Correlation**: How audio metrics relate
- **Engine Insights**: How recommendations work

### 🎭 Mood & Instrument Analyzer
- Upload MP3/WAV files
- Generate mel-spectrograms
- Analyze mood and instruments

### 🎼 Remix / Compose Studio
- AI music generation
- Song remixing capabilities

## Configuration

### Optional: Gemini API Integration

1. Get API key: https://makersuite.google.com/app/apikey

2. Create `.streamlit/secrets.toml`:
   ```toml
   GEMINI_API_KEY = "your-api-key-here"
   ```

3. Restart Streamlit to use AI explanations

Without API key, the system works with intelligent default explanations.

## File Structure
```
Song-training-test/
├── streamlit_app.py                 # Main Streamlit app
├── recommendation_engine.py         # Recommendation algorithms
├── test_recommendations.py         # Engine tests
├── requirements.txt                # Python dependencies
├── RECOMMENDATION_GUIDE.md         # Detailed documentation
├── SETUP_GUIDE.md                 # This file
└── .streamlit/
    ├── config.toml                # Streamlit config
    └── secrets.toml               # API keys (git-ignored)
```

## Troubleshooting

### ImportError: No module named 'sklearn'
```bash
pip install scikit-learn
```

### FileNotFoundError: CSV files not found
Update paths in `recommendation_engine.py` and `streamlit_app.py` to match your setup.

### Slow recommendations
- The engine loads 100,000 records by default
- Reduce `sample_size` in `recommendation_engine.py` for faster testing

### "No recommendations found"
- Try different user IDs from the dropdown
- Some users may have no similar users or unheard songs

## Performance Notes

| Metric | Value |
|--------|-------|
| Users | 9,648 |
| Songs | 15,473 |
| Sparsity | 99.96% |
| Matrix Init | ~5-10 seconds |
| Single Recommendation | ~0.5-1 second |
| Hybrid (5 recs) | ~1-2 seconds |

## API Reference

### RecommendationEngine

```python
from recommendation_engine import RecommendationEngine

# Initialize
engine = RecommendationEngine(
    music_info_path="path/to/Music Info.csv",
    listening_history_path="path/to/User Listening History.csv"
)

# Get recommendations
collab_recs = engine.collaborative_filtering(user_id, top_n=5)
content_recs = engine.content_based_filtering(user_id, top_n=5)
hybrid_recs = engine.hybrid_recommendations(user_id, top_n=5)

# User insights
prefs = engine.get_user_preferences(user_id)
users = engine.get_all_user_ids()
songs = engine.get_song_by_name("query")
```

### GeminiExplainer

```python
from recommendation_engine import GeminiExplainer

explainer = GeminiExplainer(api_key="your-key")
explanation = explainer.generate_explanation(
    recommendation=rec,
    user_preferences=prefs
)
```

## Advanced Usage

### Custom Filtering Settings
Edit `recommendation_engine.py`:
- Change `sample_size` for more/fewer records
- Adjust similarity thresholds
- Add/remove audio features

### Feature Engineering
Add new features to `song_features_matrix` in the `build_matrices()` method.

### Model Improvements
- Implement matrix factorization (SVD/NMF)
- Add implicit feedback models
- Use neural collaborative filtering

## Deployment to Cloud

### Streamlit Cloud
1. Push to GitHub repository
2. Connect at https://share.streamlit.io
3. Set environment variable for API key

### Docker
Create `Dockerfile`:
```dockerfile
FROM python:3.9

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["streamlit", "run", "streamlit_app.py"]
```

Run:
```bash
docker build -t soniqueai .
docker run -p 8501:8501 soniqueai
```

## Security Notes

⚠️ **Never commit `.streamlit/secrets.toml` to Git!**

Add to `.gitignore`:
```
.streamlit/secrets.toml
__pycache__/
*.pyc
.DS_Store
```

## Support & Issues

1. Check `RECOMMENDATION_GUIDE.md` for technical details
2. Review error messages in terminal
3. Test with `test_recommendations.py` first
4. Verify data files exist at expected paths

## License & Attribution

This recommendation system uses:
- Pandas/NumPy: Data processing
- Scikit-learn: Machine learning
- Streamlit: Web interface
- Google Generative AI: Explanations (optional)

## Version History

- **v1.0** (2024): Initial release
  - Collaborative filtering
  - Content-based filtering
  - Hybrid recommendations
  - Gemini integration
  - Analytics dashboard
