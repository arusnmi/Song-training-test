# 🎧 SoniqueAI Quick Reference Guide

## Installation (2 minutes)

```bash
# 1. Navigate to project
cd Song-training-test

# 2. Install dependencies
pip install -r requirements.txt

# 3. Test the engine
python test_recommendations.py

# 4. Run the app
streamlit run streamlit_app.py
```

App opens at: `http://localhost:8501`

---

## Using the Recommendation Feature

### Step 1: Open Recommendations Tab
Click "Recommendations" in the sidebar

### Step 2: Select a User
**Option A:** Choose from dropdown (first 100 users)
```
🔽 User Selection → Pick any user
```

**Option B:** Enter custom user ID
```
🔽 Select "Enter custom ID" → Type user ID
```

### Step 3: Choose Filtering Method

| Method | Best For | Speed | Accuracy |
|--------|----------|-------|----------|
| **Hybrid** | General use | Fast | Best |
| **Collaborative** | Similar users | Medium | Good |
| **Content-Based** | Similar songs | Fastest | Good |

### Step 4: Adjust Settings
- Slide number of recommendations: 3-10
- Default: 5 recommendations

### Step 5: Click "Get Recommendations"

Wait 1-2 seconds, then see:
- ✅ Your music profile
- ✅ Top recommendations
- ✅ Why each song is recommended
- ✅ Audio feature stats

---

## Understanding Your Results

### Your Music Profile
Shows what you typically listen to:

```
📊 Your Audio Profile
─────────────────────
Energy:       0.63 (Moderate)
Happiness:    0.43 (Neutral)
Danceability: 0.47 (Medium)
Acousticness: 0.31 (Electronic)
```

### Recommendations
Each shows:
- **Name & Artist** - Song title
- **Genre** - Music category
- **Method** - How it was found
- **Stats** - Energy, valence, danceability
- **Explanation** - Why recommended

### Example Output
```
1. Each Coming Night - Iron & Wine
   Genre: Folk
   Method: Collaborative
   Energy: 0.23 | Valence: 0.45 | Dance: 0.12
   
   💡 Why: Users like you also enjoyed this song.
```

---

## Command Line Usage

### Test the Engine
```bash
python test_recommendations.py
```

Outputs:
- ✅ Dataset info (9,648 users, 15,473 songs)
- ✅ Sample recommendations
- ✅ User preferences
- ✅ All 3 filtering methods
- ✅ Explanations

### Python Script Usage
```python
from recommendation_engine import RecommendationEngine

# Load
engine = RecommendationEngine(
    "Music Info.csv",
    "User Listening History.csv"
)

# Get recommendations
recs = engine.hybrid_recommendations("user_id", top_n=5)

# Display
for rec in recs:
    print(f"{rec['name']} - {rec['artist']}")
    print(f"  Energy: {rec['energy']:.2f}")
```

---

## Enable Gemini AI Explanations (Optional)

### Get API Key
1. Visit: https://makersuite.google.com/app/apikey
2. Copy your API key

### Configure
1. Create file: `.streamlit/secrets.toml`
2. Add line:
   ```toml
   GEMINI_API_KEY = "paste-your-key-here"
   ```
3. Restart Streamlit

### Result
explanations change from:
```
"Users like you also enjoyed this song."
```
to:
```
"Recommended because it has high energy and 
a happy mood, similar to songs you liked."
```

---

## Understanding the Algorithms

### 🤝 Collaborative Filtering
**What:** Find users like you, see what they like

**How:**
1. User A and User B both like Song X and Song Y
2. User B also likes Song Z
3. Recommend Song Z to User A

**Best for:** Popular songs, discovering trends

### 🎵 Content-Based Filtering
**What:** Find songs similar to your favorites

**How:**
1. You like Song A (high energy, happy)
2. Find other songs with high energy & happiness
3. Recommend them

**Best for:** New songs, specific moods

### 🎭 Hybrid (Recommended)
**What:** Best of both worlds

**How:**
1. Get 3-5 recommendations from collaborative filtering
2. Get 3-5 recommendations from content-based filtering
3. Merge and rank them
4. Return top 5

**Best for:** All cases, most accurate

---

## Troubleshooting

### "No recommendations found"
**Problem:** User has no similar users or has heard all available songs

**Solution:** Try different user ID from dropdown

### Slow loading (>5 seconds)
**Problem:** Loading 100,000 records of history

**Solution:** Edit `config.py`:
```python
LISTENING_HISTORY_SAMPLE_SIZE = 50000  # Reduce from 100,000
```

### ImportError
**Problem:** Missing packages

**Solution:**
```bash
pip install -r requirements.txt --upgrade
```

### File not found errors
**Problem:** Data files in wrong location

**Solution:** Check paths in `config.py`:
```python
MUSIC_INFO_CSV = "path/to/Music Info.csv"
LISTENING_HISTORY_CSV = "path/to/User Listening History.csv"
```

### Gemini errors
**Problem:** API key invalid or no internet

**Solution:** 
- Remove `.streamlit/secrets.toml`
- App uses default explanations
- Check API key is valid
- Check internet connection

---

## Tips & Tricks

### Getting Better Recommendations
1. **Use Hybrid method** - Best accuracy
2. **Adjust top N** - More options = better match
3. **Try different users** - Some users have more diversity
4. **Check Music Profile** - Understand your taste
5. **Enable Gemini** - Better explanations

### Understanding Features

| Feature | Range | Meaning |
|---------|-------|---------|
| Energy | 0-1 | Intense (0) ← → Calm (1) |
| Valence | 0-1 | Sad (0) ← → Happy (1) |
| Dance | 0-1 | Slow (0) ← → Rhythmic (1) |
| Acoustic | 0-1 | Electronic (0) ← → Acoustic (1) |

### What Makes a Good Recommendation
- ✅ Matches your energy level
- ✅ Similar genre/style
- ✅ Features align with your taste
- ✅ Something you haven't heard
- ✅ Right mood for the moment

---

## Feature Overview

### Analytics Dashboard
```
📊 Tab 1: Dataset Overview
   - Total users: 9,648
   - Total songs: 15,473
   - Genre distribution chart

📊 Tab 2: Feature Analysis
   - Energy distribution
   - Correlation matrix
   - Feature stats

📊 Tab 3: Insights
   - Engine explanation
   - Quality metrics
   - Performance stats
```

### Mood & Instrument Analyzer
```
🎭 Upload MP3/WAV
🎵 Get mel-spectrogram
🎼 Detect mood & instruments
```

### Remix / Compose Studio
```
🎼 Compose: Generate AI music
🎶 Remix: Blend two songs
🎚️ Control: Tempo & blend ratio
```

---

## Performance Guide

| Task | Time | Quality |
|------|------|---------|
| Load app | 5-10s | Start |
| Get 5 recs | 1-2s | Fast |
| Full analysis | 2-3s | Complete |
| Gemini explanation | +1-2s | Enhanced |

**Pro Tip:** First load takes longer (caching). Subsequent loads are faster.

---

## File Locations

```
Song-training-test/
├── streamlit_app.py           ← Run this
├── recommendation_engine.py   ← Core logic
├── config.py                  ← Settings
├── test_recommendations.py    ← Test this
├── requirements.txt           ← Install from
├── README.md                  ← Full docs
├── RECOMMENDATION_GUIDE.md    ← Technical
├── SETUP_GUIDE.md            ← Deployment
└── .streamlit/
    └── secrets.toml           ← Optional API key
```

---

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Test recommendation engine  
python test_recommendations.py

# Run Streamlit app
streamlit run streamlit_app.py

# View config
python config.py

# Check Python version
python --version

# Activate virtual environment (if using)
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
```

---

## Support Resources

| Question | Answer |
|----------|--------|
| How does it work? | Read RECOMMENDATION_GUIDE.md |
| How to set up? | Read SETUP_GUIDE.md |
| Got an error? | Check test_recommendations.py |
| Want to customize? | Edit config.py |
| Need quick answer? | Read this file |

---

## Key Statistics

| Metric | Value |
|--------|-------|
| Users in dataset | 9,648 |
| Songs in dataset | 15,473 |
| Total interactions | 1,000,000+ |
| Data sparsity | 99.96% |
| Audio features | 11 |
| Typical user songs | 100-1000 |
| Recommendations per query | 3-10 |
| Processing time | 1-2 seconds |

---

## Example Recommendation

```
User: 0007c0e74728ca9ef0fe4eb7f75732e8026a278b
Songs heard: 3
Avg Energy: 0.63 | Avg Valence: 0.43 | Avg Dance: 0.47

TOP RECOMMENDATIONS (Hybrid):
─────────────────────────────

1. Each Coming Night - Iron & Wine (Collaborative)
   Genre: Folk | Energy: 0.23 | Valence: 0.45
   💡 Users like you also enjoyed this song.

2. Abuse Me - Silverchair (Content-Based)
   Genre: Rock | Energy: 0.37 | Valence: 0.37
   💡 Recommended because it matches your taste.

3. Bring Me To Life - Katherine Jenkins (Collaborative)
   Genre: Rock | Energy: 0.56 | Valence: 0.55
   💡 Users like you also enjoyed this song.

4. Lonelily - Damien Rice (Content-Based)
   Genre: (unknown) | Energy: 0.42 | Valence: 0.55
   💡 Recommended because it matches your taste.

5. Golden Rule - Charles Bradley (Collaborative)
   Genre: Rock | Energy: 0.74 | Valence: 0.72
   💡 Users like you also enjoyed this song.
```

---

## Quick Check List

Before using:
- ✅ Python 3.9+ installed
- ✅ Dependencies installed (`pip install -r requirements.txt`)
- ✅ CSV files in correct location
- ✅ At least 4GB RAM available
- ✅ Internet (optional, for Gemini API)

First use:
- ✅ Run `python test_recommendations.py`
- ✅ See successful test output
- ✅ Run `streamlit run streamlit_app.py`
- ✅ App opens in browser

Ready to use:
- ✅ Select user from dropdown
- ✅ Choose recommendation method
- ✅ Click "Get Recommendations"
- ✅ View results with explanations

---

**🎵 Enjoy discovering music! Questions? Check the docs. 🤖**

Version: 1.0 | Quick Reference Guide | 2024
