# 🚀 Zorix CLI Quick Start

## Step 1: Start the Server
```bash
# In terminal 1 - Start the server
python start_zorix.py
```
*(Keep this running)*

## Step 2: Test CLI Connection
```bash
# In terminal 2 - Test CLI
python zorix_cli.py status
```

## Step 3: Basic Commands

### 💬 Chat with AI
```bash
python zorix_cli.py chat "How do I create a Python function?"
```

### 📋 Plan Tasks
```bash
# See what would be done (safe)
python zorix_cli.py plan "Create a hello world script" --dry-run

# Actually do it
python zorix_cli.py plan "Create a hello world script"
```

### 🔍 Search Code
```bash
python zorix_cli.py search "function definition"
```

### 📊 Check Status
```bash
python zorix_cli.py status
```

### ⚙️ Configure CLI
```bash
python zorix_cli.py config show
```

## 🎯 Real Examples

### Ask for Help
```bash
python zorix_cli.py chat "I'm getting a Python import error. How do I fix it?"
```

### Generate Code
```bash
python zorix_cli.py chat "Write a Python function to read a JSON file"
```

### Plan Development Tasks
```bash
python zorix_cli.py plan "Add error handling to my Python script" --dry-run
```

### Search Your Project
```bash
python zorix_cli.py search "class definition" --type code --max-results 5
```

## 🔧 Configuration

### Set Your Preferences
```bash
python zorix_cli.py config set output-format rich
python zorix_cli.py config set max-search-results 20
```

## 🚨 Troubleshooting

### CLI Not Working?
1. **Check server**: http://127.0.0.1:8000/health
2. **Check config**: `python zorix_cli.py config show`
3. **Update API URL**: `python zorix_cli.py config set api-url http://127.0.0.1:8000`

## 💡 Pro Tips

### Create Aliases
```bash
# Add to your .bashrc/.zshrc
alias zc="python zorix_cli.py chat"
alias zp="python zorix_cli.py plan"
alias zs="python zorix_cli.py search"

# Then use:
zc "How do I optimize this code?"
zp "Add tests to my functions"
zs "error handling"
```

**You're ready to use your AI coding assistant from the command line!** 🤖