# 🔧 Port Configuration Guide

## 🎯 Quick Port Change

**To change the port for your entire Zorix Agent system:**

1. **Edit `PORT_CONFIG.py`**:
   ```python
   # Change this line:
   ZORIX_PORT = 8000  # Change to your desired port
   ```

2. **Restart the server**:
   ```bash
   python start_zorix.py
   ```

3. **Done!** Everything now uses the new port.

## 📁 Files That Use Centralized Port

All these files automatically use the port from `PORT_CONFIG.py`:

- ✅ `start_zorix.py` - Main startup script
- ✅ `run_web.py` - Web server
- ✅ `simple_start.py` - Simple server
- ✅ `start_with_ai.py` - AI chat server
- ✅ `agent/config.py` - Core configuration
- ✅ `agent/cli/config.py` - CLI configuration

## 🚀 Startup Options

### Option 1: Unified Starter (Recommended)
```bash
python start_zorix.py          # Full agent
python start_zorix.py --simple # Simple version
```

### Option 2: Individual Scripts
```bash
python run_web.py        # Full web server
python simple_start.py   # Simple server
```

### Option 3: Check Port Configuration
```bash
python start_zorix.py --port-info
# or
python PORT_CONFIG.py
```

## 🌐 Access URLs

After starting, your agent will be available at:

- **Main Interface**: http://127.0.0.1:8000/
- **Chat Interface**: http://127.0.0.1:8000/static/index.html
- **API Documentation**: http://127.0.0.1:8000/docs
- **Health Check**: http://127.0.0.1:8000/health

*(Replace 8000 with your configured port)*

## 🔧 Advanced Configuration

### Environment Variable Override
You can also set the port via environment variable:
```bash
export ZORIX_PORT=9000
python start_zorix.py
```

### .env File Configuration
Add to your `.env` file:
```bash
APP_PORT=9000
```

### Priority Order
1. Environment variable `ZORIX_PORT`
2. `.env` file `APP_PORT`
3. `PORT_CONFIG.py` `ZORIX_PORT`
4. Default: 8000

## 🚨 Troubleshooting

### Port Already in Use
```bash
# Check what's using the port
netstat -an | findstr :8000  # Windows
lsof -i :8000                # Mac/Linux

# Use a different port
# Edit PORT_CONFIG.py and change ZORIX_PORT = 8001
```

### Can't Access Server
1. Check if server is running: `curl http://127.0.0.1:8000/health`
2. Check firewall settings
3. Try `127.0.0.1` instead of `localhost`

## 💡 Tips

- **Development**: Use port 8000-8999 range
- **Production**: Use port 80 (HTTP) or 443 (HTTPS)
- **Testing**: Use port 9000+ to avoid conflicts
- **Multiple instances**: Use different ports for each

## 🎯 Quick Commands

```bash
# Start with default port (8000)
python start_zorix.py

# Check current port configuration
python PORT_CONFIG.py

# Start simple version
python start_zorix.py --simple

# Show help
python start_zorix.py --help
```