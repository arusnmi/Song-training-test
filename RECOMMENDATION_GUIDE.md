# SoniqueAI - Music Recommendation System Documentation

## Overview
The recommendation engine uses **Hybrid Filtering** combining:
1. **Collaborative Filtering** - Finds users with similar listening patterns and recommends their favorite songs
2. **Content-Based Filtering** - Recommends songs with similar audio features to what you've already liked
3. **Gemini AI Integration** - Generates human-readable explanations for recommendations

## Data Requirements

### Input Files
1. **User Listening History** (`User Listening History.csv`)
   - Columns: `track_id`, `user_id`, `playcount`
   - Contains listening patterns for all users

2. **Music Info** (`Music Info.csv`)
   - Columns: `track_id`, `name`, `artist`, `genre`, and audio features
   - Audio features: `danceability`, `energy`, `valence`, `acousticness`, `instrumentalness`, `tempo`, etc.

## How It Works

### 1. Collaborative Filtering
- Builds a **User-Item Matrix** where:
  - Rows = users
  - Columns = songs
  - Values = playcount (times listened)
- **Process:**
  1. Find users with similar listening patterns to the target user
  2. Identify songs they listened to that the target user hasn't
  3. Recommend top songs weighted by listens

### 2. Content-Based Filtering
- Uses **audio features** to measure song similarity:
  - Energy (0-1): How intense/energetic
  - Valence (0-1): Musical positiveness/happiness
  - Danceability (0-1): How danceable
  - Acousticness (0-1): How acoustic vs. electronic
  - Instrumentalness (0-1): Presence of vocals
- **Process:**
  1. Calculate average feature profile of songs user likes
  2. Find similar songs using cosine similarity
  3. Recommend songs with similar features that user hasn't heard

### 3. Hybrid Approach
- Combines both methods: 3 recommendations from collaborative filtering + 3 from content-based
- Deduplicates and ranks by relevance

## Using the Recommendation Engine

### In Streamlit App
1. Navigate to **"Recommendations"** tab
2. **Select User:**
   - Choose from dropdown (first 100 users)
   - Or enter custom user ID
3. **Choose Method:**
   - Hybrid (Recommended)
   - Collaborative Filtering only
   - Content-Based Filtering only
4. **Adjust Settings:**
   - Number of recommendations (3-10)
5. **Click "Get Recommendations"**

### Output
For each recommendation, you get:
- **Song Info:** Name, artist, genre, track ID
- **Audio Stats:** Energy, happiness (valence), danceability
- **Why Recommended:** AI-generated explanation (if Gemini API configured)
- **Method:** Which filtering technique found it

### User Profile Display
Shows your music preferences:
- Total songs listened
- Average energy level
- Average happiness (valence)
- Average danceability
- Top genres
- Audio feature profile (bar chart)

## Setting Up Gemini API Integration (Optional)

### For Local Testing
1. Get a free Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create `.streamlit/secrets.toml`:
   ```toml
   GEMINI_API_KEY = "your-api-key-here"
   ```

### For Production
Set environment variable:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

If not configured, the system still works with default explanations.

## Technical Details

### Feature Normalization
- All audio features are normalized using StandardScaler
- Ensures fair similarity calculations across different feature ranges

### Similarity Metrics
- **Cosine Similarity:** Measures angle between feature vectors
- Range: -1 to 1 (closer to 1 = more similar)

### Performance Optimization
- Loads first 100,000 records of listening history for speed
- Caches recommendation engine to avoid reloading
- Uses NumPy for fast matrix operations

## Troubleshooting

### "No recommendations found"
- User ID might not exist in dataset
- Try a different user ID from the dropdown

### "Recommendation engine not initialized"
- Check file paths in code
- Ensure `Music Info.csv` and `User Listening History.csv` exist
- Verify CSV files are not corrupted

### Gemini explanations not working
- API key might be invalid
- Check internet connection
- Remove secrets.toml to use default explanations

## Example User IDs
Get sample user IDs from the dropdown in the Recommendations page.

## Future Enhancements
- [ ] Matrix factorization (SVD) for better collaborative filtering
- [ ] Deep learning models (neural collaborative filtering)
- [ ] Real-time model updates
- [ ] A/B testing for recommendation quality
- [ ] Explainability metrics (SHAP values)
- [ ] Cold-start solutions for new users
