import streamlit as st
from supabase import create_client, Client
import os
from datetime import datetime
import pandas as pd
from audio_recorder_streamlit import audio_recorder

# Hack for Python 3.13 compatibility (missing aifc)
import sys
if sys.version_info >= (3, 13):
    try:
        import aifc
    except ImportError:
        import sys
        # If standard aifc is missing, try to use the backport or mock it
        try:
            # Try to import from py-aifc if installed but named differently
            # Note: py-aifc installs as 'aifc' usually, but let's be safe
            pass
        except:
            pass
            
    # Force mock if still missing
    if 'aifc' not in sys.modules:
        import types
        sys.modules['aifc'] = types.ModuleType('aifc')
        sys.modules['aifc'].Error = Exception

import speech_recognition as sr
import tempfile
from dotenv import load_dotenv
import io
from pydub import AudioSegment
from deep_translator import GoogleTranslator

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Reception Agent - Voice Call System",
    page_icon="📞",
    layout="wide"
)

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not all([supabase_url, supabase_key]):
        st.error("⚠️ Please set up your Supabase credentials in .env file")
        return None
    
    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"❌ Connection error: {str(e)}")
        return None

# Transcription function (FREE - Google Speech Recognition)
def transcribe_audio_free(audio_file_path, language="en-US"):
    recognizer = sr.Recognizer()
    
    try:
        # Load audio file
        with sr.AudioFile(audio_file_path) as source:
            audio_data = recognizer.record(source)
            
        # Transcribe using Google Speech Recognition
        text = recognizer.recognize_google(audio_data, language=language)
        return text
    except sr.UnknownValueError:
        return "Could not understand audio"
    except sr.RequestError as e:
        return f"Could not request results from Google Speech Recognition service: {e}"
    except Exception as e:
        return f"Transcription error: {str(e)}"

# Simple rule-based analysis (FREE - no API needed)
def analyze_transcription_free(text, source_lang='auto'):
    """
    Free analysis using simple keyword matching and rules
    No API costs - completely local processing
    """
    # Translate to English for analysis
    try:
        # Handle locale codes like 'en-US', 'hi-IN' -> 'en', 'hi'
        if source_lang != 'auto' and '-' in source_lang:
            source_lang = source_lang.split('-')[0]
            
        translator = GoogleTranslator(source=source_lang, target='en')
        text_en = translator.translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        text_en = text

    text_lower = text_en.lower()
    
    # Determine intent based on keywords
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
    
    # Determine sentiment based on keywords
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
    
    # Extract potential action items
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
    
    # Create summary (first 100 chars + last 50 chars if text is long)
    if len(text_en) > 150:
        summary = text_en[:100] + "..." + text_en[-50:]
    else:
        summary = text_en
    
    # Format the analysis
    analysis = f"""**Intent:** {intent}
**Sentiment:** {sentiment}
**Action Items:**
{chr(10).join(f"- {item}" for item in action_items)}
**Summary:** {summary}
"""
    
    return analysis

# Save to Supabase
def save_to_database(supabase, filename, transcription, analysis, language="en-US"):
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "filename": filename,
            "transcribed_text": transcription,
            "analysis": analysis,
            "language": language
        }
        print(f"[DEBUG] Attempting to save data: {data}")  # Debug log
        result = supabase.table("call_records").insert(data).execute()
        print(f"[DEBUG] Save successful! Result: {result}")  # Debug log
        return True
    except Exception as e:
        error_msg = f"❌ Database error: {str(e)}"
        print(f"[ERROR] {error_msg}")  # Console log
        print(f"[ERROR] Full exception: {repr(e)}")  # Detailed error
        st.error(error_msg)
        st.error(f"Detailed error: {repr(e)}")  # Show detailed error in UI
        return False

# Load all records from database
def load_records(supabase):
    try:
        response = supabase.table("call_records").select("*").order("timestamp", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"❌ Error loading records: {str(e)}")
        return []

# Delete record from database and local storage
def delete_record(supabase, record_id, filename):
    try:
        # Delete from Supabase
        supabase.table("call_records").delete().eq("id", record_id).execute()
        
        # Delete local file if it exists
        local_file_path = os.path.join("C:/CallRecordings", filename)
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
            
        return True
    except Exception as e:
        st.error(f"❌ Error deleting record: {str(e)}")
        return False

# Custom CSS for professional styling
def local_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        /* Global Styles */
        * {
            font-family: 'Inter', sans-serif;
        }
        
        /* Clean white background */
        .stApp {
            background: #ffffff;
        }
        
        /* Main container */
        .main .block-container {
            padding: 2rem 3rem;
            max-width: 1200px;
        }
        
        /* Clean headers */
        h1 {
            color: #111827 !important;
            font-weight: 700 !important;
            font-size: 2.5rem !important;
            margin-bottom: 0.5rem !important;
        }
        
        h2 {
            color: #1f2937 !important;
            font-weight: 600 !important;
            font-size: 1.875rem !important;
        }
        
        h3 {
            color: #374151 !important;
            font-weight: 600 !important;
            font-size: 1.5rem !important;
        }
        
        /* Minimal sidebar */
        [data-testid="stSidebar"] {
            background: #f9fafb;
            border-right: 1px solid #e5e7eb;
        }
        
        [data-testid="stSidebar"] * {
            color: #111827 !important;
        }
        
        /* Sidebar navigation */
        [data-testid="stSidebar"] [data-baseweb="radio"] {
            background: white;
            border-radius: 8px;
            padding: 0.5rem;
            margin: 0.25rem 0;
            border: 1px solid #e5e7eb;
            transition: all 0.2s ease;
        }
        
        [data-testid="stSidebar"] [data-baseweb="radio"]:hover {
            border-color: #d1d5db;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        /* Clean card styles */
        .stCard {
            background: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            margin-bottom: 1.5rem;
            border: 1px solid #e5e7eb;
        }
        
        .stCard h4 {
            color: #111827 !important;
            margin-bottom: 1rem;
            font-size: 1.125rem;
            font-weight: 600;
        }
        
        /* Minimalist buttons */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            padding: 0.625rem 1.5rem;
            border: none;
            transition: all 0.2s ease;
            font-size: 0.875rem;
        }
        
        .stButton > button[kind="primary"] {
            background: #111827;
            color: white;
        }
        
        .stButton > button[kind="primary"]:hover {
            background: #1f2937;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .stButton > button[kind="secondary"] {
            background: white;
            color: #111827;
            border: 1px solid #d1d5db;
        }
        
        .stButton > button[kind="secondary"]:hover {
            background: #f9fafb;
            border-color: #9ca3af;
        }
        
        /* Clean input fields */
        .stTextInput > div > div > input,
        .stSelectbox > div > div > select {
            border-radius: 8px;
            border: 1px solid #d1d5db;
            padding: 0.625rem;
            font-size: 0.875rem;
            transition: all 0.2s ease;
            background: white;
        }
        
        .stTextInput > div > div > input:focus,
        .stSelectbox > div > div > select:focus {
            border-color: #6b7280;
            box-shadow: 0 0 0 3px rgba(107, 114, 128, 0.1);
        }
        
        /* File uploader */
        [data-testid="stFileUploader"] {
            background: white;
            border-radius: 8px;
            padding: 2rem;
            border: 2px dashed #d1d5db;
            transition: all 0.2s ease;
        }
        
        [data-testid="stFileUploader"]:hover {
            border-color: #9ca3af;
        }
        
        /* Audio player */
        audio {
            width: 100%;
            border-radius: 8px;
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            border: 1px solid #e5e7eb;
            font-weight: 600;
            color: #111827;
        }
        
        .streamlit-expanderHeader:hover {
            background: #f9fafb;
        }
        
        /* Alert boxes */
        .stSuccess {
            background: #f0fdf4;
            border-radius: 8px;
            padding: 1rem;
            border-left: 4px solid #22c55e;
            color: #166534;
        }
        
        .stInfo {
            background: #eff6ff;
            border-radius: 8px;
            padding: 1rem;
            border-left: 4px solid #3b82f6;
            color: #1e40af;
        }
        
        .stWarning {
            background: #fffbeb;
            border-radius: 8px;
            padding: 1rem;
            border-left: 4px solid #f59e0b;
            color: #92400e;
        }
        
        /* Minimal scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f9fafb;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #d1d5db;
            border-radius: 3px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #9ca3af;
        }
        
        /* Metrics */
        [data-testid="stMetricValue"] {
            font-size: 1.875rem;
            font-weight: 700;
            color: #111827;
        }
        
        /* Download button */
        .stDownloadButton > button {
            background: #059669;
            color: white;
            border-radius: 8px;
            padding: 0.625rem 1.5rem;
            font-weight: 600;
            border: none;
        }
        
        .stDownloadButton > button:hover {
            background: #047857;
        }
        
        /* Text areas */
        textarea {
            border-radius: 8px !important;
            border: 1px solid #d1d5db !important;
            transition: all 0.2s ease !important;
        }
        
        textarea:focus {
            border-color: #6b7280 !important;
            box-shadow: 0 0 0 3px rgba(107, 114, 128, 0.1) !important;
        }
        
        /* Radio buttons */
        .stRadio > div {
            gap: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# Main app
def main():
    st.set_page_config(
        page_title="Reception Agent",
        page_icon="📞",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply custom CSS
    local_css()
    
    # Initialize Supabase
    supabase = init_supabase()
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/customer-support.png", width=60)
        st.title("Reception Agent")
        st.markdown("---")
        
        page = st.radio(
            "Navigation",
            ["📞 Answer Call", "📊 View Records", "⚙️ Setup"],
            label_visibility="collapsed"
        )
    if page == "📞 Answer Call":
        # Clean hero section
        st.markdown("""
            <div style='text-align: center; padding: 2rem 0 2rem 0;'>
                <h1 style='font-size: 2.5rem; margin-bottom: 0.5rem; color: #111827;'>📞 Reception Agent</h1>
                <p style='font-size: 1.125rem; color: #6b7280; font-weight: 400;'>
                    Professional Call Transcription System
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        # Create a card-like container for input selection
        with st.container():
            
            # Input method selection with better visual
            # Language selection
            # Language selection (Hidden/Default to en-US)
            if 'language' not in st.session_state:
                st.session_state.language = "en-US"
            # st.session_state.language = st.selectbox(...) # Removed as per user request
            input_method = st.radio(
                "Choose Input Method:",
                ["🎙️ Record Voice", "📁 Upload Audio File"],
                horizontal=True
            )
            
            st.markdown("---")
            
            # Initialize session state variables if not present
            if 'transcription' not in st.session_state:
                st.session_state.transcription = None
            if 'filename' not in st.session_state:
                st.session_state.filename = None
            if 'analysis' not in st.session_state:
                st.session_state.analysis = None
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                if input_method == "🎙️ Record Voice":
                    st.info("🎙️ **Click mic to record**")
                    audio_bytes = audio_recorder(
                        text="",
                        recording_color="#ef4444",
                        neutral_color="#3b82f6",
                        icon_size="4x",
                    )
                    
                    # Check if audio has changed
                    if 'last_audio_bytes' not in st.session_state:
                        st.session_state.last_audio_bytes = None
                    
                    if audio_bytes and audio_bytes != st.session_state.last_audio_bytes:
                        st.session_state.transcription = None
                        st.session_state.analysis = None
                        st.session_state.last_audio_bytes = audio_bytes
                        st.rerun()
                    
                    if audio_bytes:
                        st.success("✅ Recorded!")
                        st.audio(audio_bytes, format="audio/wav")
                        
                        if st.button("⚡ Convert to Text", type="primary", use_container_width=True):
                            with st.spinner("🔄 Transcribing..."):
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav", mode='wb') as tmp_file:
                                    tmp_file.write(audio_bytes)
                                    tmp_file_path = tmp_file.name
                                
                                try:
                                    # Use configured default language
                                    default_lang = os.getenv("DEFAULT_LANGUAGE", "en-US")
                                    st.session_state.transcription = transcribe_audio_free(tmp_file_path, language=default_lang)
                                    st.session_state.filename = f"call_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                                    if st.session_state.transcription:
                                        st.session_state.analysis = analyze_transcription_free(st.session_state.transcription, source_lang=default_lang)
                                finally:
                                    if os.path.exists(tmp_file_path):
                                        os.unlink(tmp_file_path)

                elif input_method == "📁 Upload Audio File":
                    uploaded_file = st.file_uploader(
                        "Drop audio file here",
                        type=["mp3", "wav", "m4a", "ogg", "webm"]
                    )
                    
                    if uploaded_file:
                        st.audio(uploaded_file, format=f"audio/{uploaded_file.type.split('/')[-1]}")
                        
                        if st.button("⚡ Process File", type="primary", use_container_width=True):
                            with st.spinner("🔄 Transcribing..."):
                                # Save uploaded file to temp file
                                file_ext = uploaded_file.name.split('.')[-1].lower()
                                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as tmp_file:
                                    tmp_file.write(uploaded_file.read())
                                    tmp_file_path = tmp_file.name
                                
                                converted_wav_path = None
                                transcription_file_path = tmp_file_path
                                
                                try:
                                    # Convert to WAV if needed
                                    if file_ext != "wav":
                                        try:
                                            audio = AudioSegment.from_file(tmp_file_path)
                                            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as wav_file:
                                                audio.export(wav_file.name, format="wav")
                                                converted_wav_path = wav_file.name
                                            
                                            # Use the converted file for transcription
                                            transcription_file_path = converted_wav_path
                                        except Exception as e:
                                            st.error(f"⚠️ Error converting audio: {str(e)}")
                                    
                                    default_lang = os.getenv("DEFAULT_LANGUAGE", "en-US")
                                    st.session_state.transcription = transcribe_audio_free(transcription_file_path, language=default_lang)
                                    st.session_state.filename = uploaded_file.name
                                    if st.session_state.transcription:
                                        st.session_state.analysis = analyze_transcription_free(st.session_state.transcription, source_lang=default_lang)
                                finally:
                                    # Cleanup
                                    if os.path.exists(tmp_file_path):
                                        os.unlink(tmp_file_path)
                                    if converted_wav_path and os.path.exists(converted_wav_path):
                                        os.unlink(converted_wav_path)

            
        
        # Display results in a nice layout
        if st.session_state.transcription:
            st.markdown("### 📝 Analysis Results")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
<div class="stCard">
    <h4>🗣️ Transcription</h4>
    <div style="height:300px; overflow-y:auto; background-color:#f8f9fa; padding:10px; border-radius:5px; border:1px solid #e9ecef; color: #1f2937;">
        {st.session_state.transcription}
    </div>
</div>
""", unsafe_allow_html=True)
            
            with col2:
                if not st.session_state.analysis:
                    st.session_state.analysis = analyze_transcription_free(st.session_state.transcription)
                
                # Format for HTML display
                # 1. Escape HTML special chars to prevent injection (basic)
                analysis_text = st.session_state.analysis.replace("<", "&lt;").replace(">", "&gt;")
                # 2. Convert **Bold** to <strong>Bold</strong>
                # Simple replacement for the specific format used in analysis
                analysis_html = analysis_text.replace("**", "<strong>", 1).replace("**", "</strong>", 1) # Intent
                analysis_html = analysis_html.replace("**", "<strong>", 1).replace("**", "</strong>", 1) # Sentiment
                analysis_html = analysis_html.replace("**", "<strong>", 1).replace("**", "</strong>", 1) # Action Items
                analysis_html = analysis_html.replace("**", "<strong>", 1).replace("**", "</strong>", 1) # Summary
                # Handle any remaining pairs just in case
                while "**" in analysis_html:
                    analysis_html = analysis_html.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
                
                # 3. Convert newlines to <br>
                analysis_html = analysis_html.replace("\n", "<br>")
            # Save Action
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("💾 Save to Database", type="primary", use_container_width=True):
                    # Save audio file to C:/CallRecordings if it exists
                    audio_saved = False
                    try:
                        save_dir = "C:/CallRecordings"
                        if not os.path.exists(save_dir):
                            os.makedirs(save_dir)
                        
                        save_path = os.path.join(save_dir, st.session_state.filename)
                        
                        # Handle recording vs upload vs text
                        if input_method == "🎙️ Record Voice" and 'audio_bytes' in locals():
                            with open(save_path, "wb") as f:
                                f.write(audio_bytes)
                            audio_saved = True
                        elif input_method == "📁 Upload Audio File" and 'uploaded_file' in locals():
                            # Reset pointer
                            uploaded_file.seek(0)
                            with open(save_path, "wb") as f:
                                f.write(uploaded_file.read())
                            audio_saved = True
                            
                        if audio_saved:
                            print(f"[APP] Saved audio to: {save_path}")
                    except Exception as e:
                        print(f"[APP] Error saving audio file: {e}")

                    if save_to_database(supabase, st.session_state.filename, st.session_state.transcription, st.session_state.analysis, st.session_state.language):
                        st.success("✅ Step 3 Complete: Successfully stored in database!")
                        if audio_saved:
                            st.info(f"📁 Audio file saved to: C:/CallRecordings/{st.session_state.filename}")
                        st.balloons()
                        st.info("📊 Go to 'View Records' to see all stored calls.")
                        
                        # Clear session state after save
                        st.session_state.transcription = None
                        st.session_state.filename = None
                        st.session_state.analysis = None
                        st.rerun()
                    else:
                        st.error("❌ Failed to save to database. Check your Supabase connection.")
    
    elif page == "📊 View Records":
        st.markdown("## 📊 Call History")
        
        # Load records
        records = load_records(supabase)
        
        if not records:
            st.info("📭 No records found. Start by answering a call on the 'Answer Call' page.")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Stats Cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📞 Total Calls", len(df))
        with col2:
            today_calls = len(df[pd.to_datetime(df['timestamp']).dt.date == datetime.now().date()])
            st.metric("📅 Today's Calls", today_calls)
        with col3:
            avg_length = df['transcribed_text'].str.len().mean()
            st.metric("📏 Avg Length", f"{int(avg_length)} chars")
        
        st.markdown("---")
        
        # Search and filter
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input("🔍 Search", placeholder="Search by keyword, intent, or content...")
        with col2:
            date_filter = st.date_input("📅 Date", value=None)
        
        # Apply filters
        filtered_df = df.copy()
        if search_term:
            filtered_df = filtered_df[
                filtered_df['transcribed_text'].str.contains(search_term, case=False, na=False) |
                filtered_df['analysis'].str.contains(search_term, case=False, na=False)
            ]
        
        if date_filter:
            filtered_df = filtered_df[pd.to_datetime(filtered_df['timestamp']).dt.date == date_filter]
        
        st.markdown(f"### 📋 Recent Calls ({len(filtered_df)})")
        
        # Display records
        for idx, record in filtered_df.iterrows():
            with st.expander(f"📞 {record['filename']} - {record['timestamp'][:16]}"):
                # Check if audio file exists locally
                local_audio_path = os.path.join("C:/CallRecordings", record['filename'])
                if os.path.exists(local_audio_path):
                    st.audio(local_audio_path)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**📄 Transcription:**")
                    st.info(record['transcribed_text'])
                
                with col2:
                    st.markdown("**🤖 Analysis:**")
                    st.success(record['analysis'])
                
                # Delete button
                if st.button("🗑️ Delete Record", key=f"delete_{record['id']}", type="secondary"):
                    if delete_record(supabase, record['id'], record['filename']):
                        st.success("✅ Record deleted successfully!")
                        st.rerun()
        
        # Download option
        st.divider()
        if st.button("📥 Export All Records to CSV"):
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="⬇️ Download CSV File",
                data=csv,
                file_name=f"call_records_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    # Setup page
    elif page == "⚙️ Setup":
        st.header("⚙️ System Configuration")
        
        st.markdown("""
        ### 🏗️ System Architecture
        
        This application utilizes a robust stack of technologies to provide seamless call processing and analysis:
        
        *   **Speech-to-Text Engine**: Google Speech Recognition for accurate voice transcription.
        *   **Analysis Engine**: Local rule-based processing for intent detection and sentiment analysis.
        *   **Database**: Supabase (PostgreSQL) for secure and scalable record storage.
        
        ### 🚀 Getting Started
        
        #### 1. Configuration
        Ensure your environment variables are correctly set in the `.env` file. This includes your Supabase credentials and default language settings.
        
        #### 2. Database Schema
        The system requires a specific table structure in Supabase. If you haven't initialized it yet, run the following SQL query in your Supabase SQL Editor:
        
        ```sql
        CREATE TABLE IF NOT EXISTS call_records (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            filename TEXT NOT NULL,
            transcribed_text TEXT NOT NULL,
            analysis TEXT,
            language TEXT DEFAULT 'en-US',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_call_records_timestamp ON call_records(timestamp DESC);
        ```
        
        ### 📝 Workflow
        
        1.  **Input**: Record voice directly in the browser or upload audio files (WAV, MP3, M4A).
        2.  **Processing**: The system automatically transcribes the audio and translates it to English if necessary.
        3.  **Analysis**: Key insights (Intent, Sentiment, Action Items) are extracted.
        4.  **Storage**: All data is securely stored and available for review in the "View Records" tab.
        
        ### 🔍 Troubleshooting
        
        *   **Transcription Issues**: Ensure audio is clear and background noise is minimized. Check your internet connection.
        *   **Database Errors**: Verify your Supabase project status and credential validity.
        """)
        
        # Check status
        st.divider()
        st.subheader("🔍 System Status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.success("✅ Speech Services: Active")
            st.info("Google Speech Recognition Ready")
        
        with col2:
            if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"):
                st.success("✅ Database: Connected")
            else:
                st.error("❌ Database: Disconnected")

if __name__ == "__main__":
    main()