import pandas as pd
import os

# Check User Listening History
listening_file = r"c:\Users\warty\OneDrive\Desktop\Python_projects\Capstone_music_maker\Scenario 2_ AI Music Composer & Listener Insight platform\User Listening History.csv"
print("Reading User Listening History...")
df_listening = pd.read_csv(listening_file, nrows=10)
print("\nColumns:", df_listening.columns.tolist())
print("\nFirst few rows:")
print(df_listening.head())
print(f"\nShape: {df_listening.shape}")
