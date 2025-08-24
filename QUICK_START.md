# 🚀 Zorix Agent - Quick Start Guide

## Fastest Way to Run

### Option 1: One-Command Start
```bash
python start.py
```
This will:
- ✅ Check and install dependencies automatically
- 🌐 Start the server on an available port
- 🌍 Open your browser automatically
- 📚 Show you all available endpoints

### Option 2: Simple Server
```bash
python run_simple.py
```

### Option 3: Manual FastAPI
```bash
# Install dependencies first
pip install fastapi uvicorn

# Then run
python -c "
import uvicorn
from fastapi import FastAPI

app = FastAPI(title='Zorix Agent')

@app.get('/')
def root():
    return {'message': 'Zorix Agent is running!', 'status': 'healthy'}

@app.get('/health')
def health():
    return {'status': 'healthy'}

uvicorn.run(app, host='127.0.0.1', port=8001)
"
```

## What You'll Get

Once running, you can access:

- **🏠 Home**: http://127.0.0.1:8001/ - Main endpoint
- **❤️ Health**: http://127.0.0.1:8001/health - Health check
- **📚 Docs**: http://127.0.0.1:8001/docs - Interactive API documentation
- **📊 Status**: http://127.0.0.1:8001/status - System status

## Current Status

This is a **minimal working version** that provides:
- ✅ Basic web server
- ✅ Health checks
- ✅ API documentation
- ✅ Status endpoints

## Next Steps for Full Features

To get the complete Zorix Agent with AI capabilities:

1. **AWS Setup**: Configure AWS Bedrock access
2. **Environment**: Set up `.env` file with credentials
3. **Dependencies**: Install all requirements: `pip install -r requirements.txt`
4. **Full System**: Run the complete system

## Troubleshooting

### Port Already in Use
If you get a port error, the start script will automatically find an available port.

### Missing Dependencies
The start script will automatically install FastAPI and Uvicorn.

### Import Errors
If you see import errors, run:
```bash
pip install fastapi uvicorn
```

## Testing the API

Once running, test with curl:
```bash
# Health check
curl http://127.0.0.1:8001/health

# Status
curl http://127.0.0.1:8001/status

# Root endpoint
curl http://127.0.0.1:8001/
```

## Stop the Server

Press `Ctrl+C` in the terminal to stop the server.

---

**🎉 Congratulations!** You now have Zorix Agent running locally. Visit the `/docs` endpoint to explore the API interactively.