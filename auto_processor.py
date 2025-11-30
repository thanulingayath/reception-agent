import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import speech_recognition as sr
from pydub import AudioSegment
from deep_translator import GoogleTranslator

# Load environment variables
load_dotenv()

# Initialize Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

# Default language for transcription
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en-US")
print(f"🌍 Default Language: {DEFAULT_LANGUAGE}")

# Folder to monitor
WATCH_FOLDER = "C:/CallRecordings"  # You can change this path

print("=" * 60)
print("🎙️ AUTOMATIC CALL RECORDER PROCESSOR")
print("=" * 60)
print(f"📁 Watching folder: {WATCH_FOLDER}")
print("=" * 60)

# Transcription function
def transcribe_audio_free(audio_file_path):
    """Transcribe audio using free Google Speech Recognition"""
    try:
        recognizer = sr.Recognizer()
        
        print(f"[TRANSCRIBE] Converting: {os.path.basename(audio_file_path)}")
        # Convert audio to WAV format if needed
        audio = AudioSegment.from_file(audio_file_path)
        wav_path = audio_file_path.replace(audio_file_path.split('.')[-1], 'wav')
        audio.export(wav_path, format='wav')
        
        # Transcribe using Google Speech Recognition (FREE)
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language=DEFAULT_LANGUAGE)
        
        # Clean up temporary wav file
        if wav_path != audio_file_path and os.path.exists(wav_path):
            os.unlink(wav_path)
        
        print(f"[TRANSCRIBE] Success! Text: {text[:100]}...")
        return text
    except sr.UnknownValueError:
        print("[TRANSCRIBE] ERROR: Could not understand the audio")
        return "Could not understand the audio"
    except sr.RequestError as e:
        print(f"[TRANSCRIBE] ERROR: Request error: {e}")
        return f"Error: {str(e)}"
    except Exception as e:
        print(f"[TRANSCRIBE] ERROR: {str(e)}")
        return f"Error: {str(e)}"

# Analysis function
def analyze_transcription_free(text, source_lang='auto'):
    """Free analysis using keyword matching"""
    # Translate to English for analysis
    # Always use 'auto' to detect the language automatically
    try:
        translator = GoogleTranslator(source='auto', target='en')
        text_en = translator.translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        text_en = text

    text_lower = text_en.lower()
    
    # Determine intent
    intent = "General Inquiry"
    if any(word in text_lower for word in ["buy", "purchase", "order", "price", "cost"]):
        intent = "Sales/Purchase Inquiry"
    elif any(word in text_lower for word in ["problem", "issue", "not working", "broken", "fix", "help"]):
        intent = "Technical Support"
    elif any(word in text_lower for word in ["cancel", "refund", "return", "complaint"]):
        intent = "Complaint/Refund Request"
    elif any(word in text_lower for word in ["information", "details", "tell me", "what is", "how to"]):
        intent = "Information Request"
    elif any(word in text_lower for word in ["appointment", "schedule", "book", "meeting"]):
        intent = "Appointment/Scheduling"
    
    # Determine sentiment
    positive_words = ["thank", "great", "good", "excellent", "happy", "satisfied", "love", "appreciate"]
    negative_words = ["bad", "terrible", "awful", "hate", "angry", "frustrated", "disappointed", "poor"]
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count > negative_count:
        sentiment = "Positive 😊"
    elif negative_count > positive_count:
        sentiment = "Negative 😞"
    else:
        sentiment = "Neutral 😐"
    
    # Extract action items
    action_items = []
    if "call back" in text_lower or "callback" in text_lower:
        action_items.append("Schedule callback")
    if "email" in text_lower and ("send" in text_lower or "forward" in text_lower):
        action_items.append("Send email with information")
    if "refund" in text_lower or "return" in text_lower:
        action_items.append("Process refund/return request")
    if "appointment" in text_lower or "schedule" in text_lower:
        action_items.append("Schedule appointment")
    if not action_items:
        action_items.append("Follow up with customer")
    
    # Create summary
    if len(text_en) > 150:
        summary = text_en[:100] + "..." + text_en[-50:]
    else:
        summary = text_en
    
    # Format analysis
    analysis = f"""**Intent:** {intent}
128: **Sentiment:** {sentiment}
129: **Action Items:**
130: {chr(10).join(f"- {item}" for item in action_items)}
131: **Summary:** {summary}
132: 
133: *Processed automatically by folder watcher*
134: """
    
    return analysis

# Save to database
def save_to_database(filename, transcription, analysis):
    """Save call record to Supabase database"""
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "transcribed_text": transcription,
            "analysis": analysis
        }
        print(f"[DATABASE] Saving: {filename}")
        result = supabase.table("call_records").insert(data).execute()
        print(f"[DATABASE] ✅ Saved successfully!")
        return True
    except Exception as e:
        print(f"[DATABASE] ❌ ERROR: {str(e)}")
        return False

# File system event handler
class AudioFileHandler(FileSystemEventHandler):
    def __init__(self):
        self.processing = set()  # Track files being processed
        self.processed_files = set()  # Track already processed files (avoid duplicates)
    
    def on_created(self, event):
        # Ignore directories
        if event.is_directory:
            return
        
        # Check if it's an audio file
        filepath = event.src_path
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext not in ['.mp3', '.wav', '.m4a', '.ogg', '.webm']:
            return
        
        # Get base filename without extension (to detect duplicates)
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        
        # Skip if we've already processed this base filename
        if base_name in self.processed_files:
            print(f"⏭️  Skipping duplicate: {os.path.basename(filepath)} (already processed)")
            return
        
        # Avoid processing the same file multiple times
        if filepath in self.processing:
            return
        
        self.processing.add(filepath)
        
        print("\n" + "=" * 60)
        print(f"📞 NEW AUDIO FILE DETECTED!")
        print(f"📁 File: {os.path.basename(filepath)}")
        print("=" * 60)
        
        # Wait a moment for file to be fully written
        time.sleep(2)
        
        try:
            # Check if file already exists in database
            filename = os.path.basename(filepath)
            existing = supabase.table("call_records").select("id").eq("filename", filename).execute()
            
            if existing.data:
                print(f"⏭️  Skipping: {filename} (already in database)")
                self.processed_files.add(base_name)
                return

            # Transcribe
            transcription = transcribe_audio_free(filepath)
            
            # Analyze
            print("[ANALYZE] Analyzing transcription...")
            analysis = analyze_transcription_free(transcription)
            
            # Save to database
            filename = os.path.basename(filepath)
            success = save_to_database(filename, transcription, analysis)
            
            if success:
                # Mark this base filename as processed
                self.processed_files.add(base_name)
                print("✅ PROCESSING COMPLETE!")
                print(f"📝 Transcription: {transcription[:100]}...")
                print("=" * 60 + "\n")
            else:
                print("❌ FAILED TO SAVE TO DATABASE")
                print("=" * 60 + "\n")
        
        except Exception as e:
            print(f"❌ ERROR PROCESSING FILE: {str(e)}")
            print("=" * 60 + "\n")
        
        finally:
            self.processing.remove(filepath)
    
    def on_deleted(self, event):
        """Handle file deletion - also delete from database"""
        # Ignore directories
        if event.is_directory:
            return
        
        # Check if it's an audio file
        filepath = event.src_path
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext not in ['.mp3', '.wav', '.m4a', '.ogg', '.webm']:
            return
        
        filename = os.path.basename(filepath)
        base_name = os.path.splitext(filename)[0]
        
        print("\n" + "=" * 60)
        print(f"🗑️  FILE DELETED FROM FOLDER!")
        print(f"📁 File: {filename}")
        print("=" * 60)
        
        try:
            # Delete from database
            print(f"[DATABASE] Deleting record: {filename}")
            result = supabase.table("call_records").delete().eq("filename", filename).execute()
            
            # Also remove from processed files set
            if base_name in self.processed_files:
                self.processed_files.remove(base_name)
            
            print(f"[DATABASE] ✅ Record deleted from database!")
            print("=" * 60 + "\n")
        
        except Exception as e:
            print(f"[DATABASE] ❌ Error deleting: {str(e)}")
            print("=" * 60 + "\n")

def main():
    # Create watch folder if it doesn't exist
    if not os.path.exists(WATCH_FOLDER):
        os.makedirs(WATCH_FOLDER)
        print(f"✅ Created folder: {WATCH_FOLDER}")
    
    print(f"\n📂 INSTRUCTIONS:")
    print(f"1. Save your call recordings to: {WATCH_FOLDER}")
    print(f"2. This program will automatically process them!")
    print(f"3. View results at: http://localhost:8501")
    print(f"\n🔄 Monitoring for new files... (Press Ctrl+C to stop)\n")
    
    # Set up file system observer
    event_handler = AudioFileHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_FOLDER, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping folder watcher...")
        observer.stop()
    
    observer.join()
    print("✅ Folder watcher stopped.")

if __name__ == "__main__":
    main()
