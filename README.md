# 📞 Reception Agent - Multilingual Call Transcription System

A professional Streamlit-based call transcription system that converts audio in any language to English text with AI-powered analysis.

## ✨ Features

- 🎙️ **Live Audio Recording** - Record calls directly in the browser
- 📁 **File Upload** - Support for MP3, WAV, M4A, OGG, and other formats
- 🌍 **Multilingual** - Transcribe audio in any language (Hindi, Kannada, Tamil, etc.)
- 🔄 **Auto-Translation** - Automatically translates to English for analysis
- 📊 **Call History** - View and search all transcribed calls
- 💾 **Database Storage** - Stores all records in Supabase
- 🤖 **Automated Processing** - Background processor for folder monitoring (optional)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
DEFAULT_LANGUAGE=en-US
```

### 3. Run the Application

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## 📦 Project Structure

```
reception-agent/
├── app.py                    # Main Streamlit application
├── auto_processor.py         # Background folder watcher (optional)
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create this)
├── .gitignore               # Git ignore file
├── .streamlit/
│   └── config.toml          # Streamlit configuration
├── README.md                # This file
├── DEPLOYMENT.md            # Deployment instructions
└── GITHUB_UPLOAD_STEPS.md   # GitHub upload guide
```

## 🌍 Language Support

Set `DEFAULT_LANGUAGE` in `.env` to match your primary language:

| Language | Code |
|----------|------|
| English (US) | `en-US` |
| Hindi | `hi-IN` |
| Kannada | `kn-IN` |
| Tamil | `ta-IN` |
| Telugu | `te-IN` |
| Malayalam | `ml-IN` |
| Spanish | `es-ES` |
| French | `fr-FR` |
| German | `de-DE` |
| Chinese | `zh-CN` |

## 🔧 Optional: Auto-Processor

Run the background processor to automatically transcribe files placed in a folder:

```bash
python auto_processor.py
```

This monitors `C:/CallRecordings` for new audio files and processes them automatically.

## 📊 Database Setup

1. Create a Supabase account at https://supabase.com
2. Create a new project
3. Create a table named `call_records` with these columns:
   - `id` (int8, primary key)
   - `timestamp` (timestamptz)
   - `filename` (text)
   - `transcribed_text` (text)
   - `analysis` (text)
   - `language` (text)

## 🚀 Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for instructions on deploying to Streamlit Cloud.

## 📝 How It Works

1. **Audio Input**: User records or uploads audio
2. **Speech-to-Text**: Uses Google Speech Recognition (free)
3. **Translation**: Automatically translates to English using deep-translator
4. **Analysis**: Analyzes intent, sentiment, and action items
5. **Storage**: Saves to Supabase database
6. **Display**: Shows transcription and analysis results

## 🛠️ Technologies Used

- **Streamlit** - Web interface
- **SpeechRecognition** - Speech-to-text conversion
- **deep-translator** - Language translation
- **Supabase** - Database storage
- **pydub** - Audio processing
- **watchdog** - File system monitoring