import sqlite3

# Connect (or create) database file
conn = sqlite3.connect("transcripts.db")
c = conn.cursor()

# Create table if it doesn't exist
c.execute('''CREATE TABLE IF NOT EXISTS transcripts
             (id INTEGER PRIMARY KEY,
              audio_file TEXT,
              transcription TEXT,
              translation TEXT,
              language TEXT)''')

# Read transcription and translation
with open("transcription.txt", "r", encoding="utf-8") as f:
    transcription = f.read()

with open("translation.txt", "r", encoding="utf-8") as f:
    translation = f.read()

# Insert data
audio_file_name = input("Enter the audio file name again for the database record: ")
target_lang = input("Enter the translation language code again: ")

c.execute('''INSERT INTO transcripts (audio_file, transcription, translation, language)
             VALUES (?, ?, ?, ?)''',
          (audio_file_name, transcription, translation, target_lang))

# Save and close
conn.commit()
conn.close()

print("✅ Data saved to transcripts.db")
