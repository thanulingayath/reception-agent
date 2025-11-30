# Reception Agent - Deployment Guide

## 🚀 How to Deploy to Streamlit Cloud

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin YOUR_GITHUB_URL
git push -u origin main
```

### 2. Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io/
2. Sign in with your GitHub account
3. Click "New app"
4. Select your repository: `reception-agent`
5. Main file path: `app.py`
6. Click "Deploy"

### 3. Add Secrets

In Streamlit Cloud dashboard, go to your app settings and add these secrets:

```toml
# .streamlit/secrets.toml format

SUPABASE_URL = "https://ydwgjcjrnpmcpdedsoaw.supabase.co"
SUPABASE_KEY = "your_supabase_key_here"
DEFAULT_LANGUAGE = "en-US"
```

### 4. Get Your Demo Link

Once deployed, you'll get a URL like:
```
https://username-reception-agent-app-xyz123.streamlit.app
```

Use this link for your form submission!

---

## ⚠️ Important Notes

- The `auto_processor.py` won't work on Streamlit Cloud (it needs local file system access)
- Only the main `app.py` web interface will be deployed
- Users can record/upload audio and get transcriptions in the cloud version

## 🔧 Alternative: Gradio Deployment

If you prefer Gradio, you can deploy on Hugging Face Spaces for free.
