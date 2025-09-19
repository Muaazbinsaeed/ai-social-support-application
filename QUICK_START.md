# 🚀 Quick Start Guide - AI Social Support Application

**Get the system running in 5 minutes!**

## ✅ Prerequisites Check

Before starting, ensure you have:
- Python 3.9+ (we tested with 3.13.1)
- 4GB+ RAM available
- 2GB free disk space
- Terminal/Command prompt access

## 📋 Step-by-Step Setup

### 1. Install Ollama (2 minutes)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# In a NEW terminal, install the model
ollama pull qwen2:1.5b
```

**✅ Verify**: `ollama list` should show `qwen2:1.5b`

### 2. Setup Project (1 minute)

```bash
# Navigate to project
cd ai-social-support

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Start the Application (1 minute)

Open **3 terminals** and run these commands:

**Terminal 1 - Main API:**
```bash
cd ai-social-support
source venv/bin/activate
cd backend/api
python -m uvicorn simple_server:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Chat API:**
```bash
cd ai-social-support
source venv/bin/activate
cd backend/api
python -m uvicorn chat_server:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 3 - Frontend:**
```bash
cd ai-social-support
source venv/bin/activate
cd frontend
streamlit run app.py --server.port 8501
```

### 4. Test the System (1 minute)

**Open your browser to**: http://localhost:8501

**Quick Test Checklist:**
- [ ] Can you see the application form?
- [ ] Can you submit an application?
- [ ] Can you chat with the AI assistant?
- [ ] Can you upload documents?

## 🎯 System Health Check

Run this quick test to verify everything is working:

```bash
cd ai-social-support
source venv/bin/activate

python -c "
import requests

services = [
    ('Frontend', 'http://localhost:8501'),
    ('Main API', 'http://localhost:8000/health'),
    ('Chat API', 'http://localhost:8001/chat/health'),
    ('Ollama', 'http://localhost:11434/api/tags')
]

print('=== System Status Check ===')
for name, url in services:
    try:
        r = requests.get(url, timeout=3)
        status = '✅ OK' if r.status_code == 200 else f'❌ Error {r.status_code}'
        print(f'{name}: {status}')
    except:
        print(f'{name}: ❌ OFFLINE')
"
```

**Expected Output:**
```
=== System Status Check ===
Frontend: ✅ OK
Main API: ✅ OK
Chat API: ✅ OK
Ollama: ✅ OK
```

## 🔧 Troubleshooting

### Problem: "Ollama connection failed"
**Solution:**
```bash
# Check if Ollama is running
ollama ps

# If not running, start it
ollama serve

# Verify model is available
ollama list
```

### Problem: "Port already in use"
**Solution:**
```bash
# Kill processes on ports 8000, 8001, 8501
lsof -ti:8000 | xargs kill -9
lsof -ti:8001 | xargs kill -9
lsof -ti:8501 | xargs kill -9

# Then restart the services
```

### Problem: "Module not found"
**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Problem: "Slow chat responses"
**Solution:**
- Simple greetings should be instant (<0.1s)
- Complex questions take 5-6 seconds
- If slower, check system RAM and CPU usage

## 🎮 How to Use

### 1. Submit an Application
1. Fill out the form with your information
2. Click "Submit Application"
3. Note your Application ID

### 2. Upload Documents
1. Go to "Document Upload" tab
2. Select files (PDF, JPG, PNG, XLSX, DOCX)
3. Choose document type for each file
4. Click "Upload Documents"

### 3. Chat with AI Assistant
1. Go to "Interactive Assistant" tab
2. Try these example questions:
   - "Hi"
   - "What documents do I need?"
   - "How can you help me?"
   - "What are the eligibility requirements?"

### 4. Check Results
1. Go to "Application Results" tab
2. View your application status
3. Monitor processing progress

## 🌟 Features to Try

**✅ Instant Chat Responses:**
- "hi", "hello", "hey" → Instant response
- "how can you help me?" → Instant FAQ

**✅ Document Upload:**
- Multiple file upload
- Type classification
- Size validation (200MB max)

**✅ Persistent Storage:**
- Applications survive server restarts
- Data stored in `data/temp/`

**✅ Real-time Status:**
- Live application tracking
- Processing progress updates

## 🎯 Success Indicators

You'll know the system is working perfectly when:

1. **Frontend loads** at http://localhost:8501
2. **Form submission** creates an application ID
3. **Chat responds instantly** to greetings
4. **Documents upload** successfully with validation
5. **Application data persists** across server restarts

## 🚨 Getting Help

If you encounter issues:

1. **Check the logs**: Look for error messages in the terminal windows
2. **Verify services**: Use the health check script above
3. **Restart services**: Close terminals and restart the 3-step process
4. **Check system resources**: Ensure 4GB+ RAM available

## ⚡ Pro Tips

1. **Keep Ollama running**: Start `ollama serve` first and keep it running
2. **Use 3 terminals**: Don't try to run everything in one terminal
3. **Check health endpoints**: Use `/health` URLs to debug issues
4. **Monitor RAM usage**: qwen2:1.5b needs ~2GB RAM
5. **File validation**: Stick to supported formats (PDF, JPG, PNG, XLSX, DOCX)

---

## 🎉 You're Ready!

Once all services are running and the health check passes, you have a **fully functional AI Social Support Application System** with:

- ✅ Smart chat assistant
- ✅ Document processing
- ✅ Application management
- ✅ Local privacy (no external services)
- ✅ Persistent data storage

**Enjoy your AI-powered social support system!** 🚀