#!/usr/bin/env python3
"""
Startup script for AI Social Support Application with Authentication
Runs all required services: Auth API, Main API, Chat API, and Frontend
"""

import subprocess
import threading
import time
import os
import signal
import sys
from pathlib import Path

# Server configurations
SERVERS = [
    {
        "name": "Authentication API",
        "command": ["python", "-m", "uvicorn", "backend.api.auth_server:app", "--host", "0.0.0.0", "--port", "8002", "--reload"],
        "port": 8002,
        "url": "http://localhost:8002",
        "health_endpoint": "/auth/health"
    },
    {
        "name": "Main API Server",
        "command": ["python", "-m", "uvicorn", "backend.api.simple_server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        "port": 8000,
        "url": "http://localhost:8000",
        "health_endpoint": "/health"
    },
    {
        "name": "Chat API Server",
        "command": ["python", "-m", "uvicorn", "backend.api.chat_server:app", "--host", "0.0.0.0", "--port", "8001", "--reload"],
        "port": 8001,
        "url": "http://localhost:8001",
        "health_endpoint": "/chat/health"
    },
    {
        "name": "Streamlit Frontend",
        "command": ["streamlit", "run", "frontend/app.py", "--server.port", "8501"],
        "port": 8501,
        "url": "http://localhost:8501",
        "health_endpoint": None
    }
]

# Global list to track processes
processes = []

def run_server(server_config):
    """Run a single server"""
    try:
        print(f"🚀 Starting {server_config['name']} on port {server_config['port']}...")

        # Change to project directory
        os.chdir(Path(__file__).parent)

        process = subprocess.Popen(
            server_config['command'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        processes.append(process)

        # Print output
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[{server_config['name']}] {line.strip()}")

    except Exception as e:
        print(f"❌ Failed to start {server_config['name']}: {e}")

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")

    required_packages = [
        "fastapi", "uvicorn", "streamlit", "sqlalchemy",
        "bcrypt", "PyJWT", "python-jose", "requests"
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("📦 Install with: pip install -r requirements.txt")
        return False

    print("✅ All dependencies are installed")
    return True

def check_ollama():
    """Check if Ollama is running"""
    print("🤖 Checking Ollama service...")

    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama is running")
            return True
        else:
            print("⚠️ Ollama is not responding properly")
            return False
    except Exception:
        print("❌ Ollama is not running")
        print("🔧 Start Ollama with: ollama serve")
        print("📥 Install model with: ollama pull qwen2:1.5b")
        return False

def wait_for_startup():
    """Wait for servers to start up"""
    print("⏳ Waiting for servers to start...")
    time.sleep(10)

    # Check server health
    import requests

    for server in SERVERS[:3]:  # Skip frontend health check
        if server["health_endpoint"]:
            try:
                response = requests.get(
                    server["url"] + server["health_endpoint"],
                    timeout=5
                )
                if response.status_code == 200:
                    print(f"✅ {server['name']} is healthy")
                else:
                    print(f"⚠️ {server['name']} returned status {response.status_code}")
            except Exception as e:
                print(f"❌ {server['name']} health check failed: {e}")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Shutting down all servers...")

    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        except Exception as e:
            print(f"Error stopping process: {e}")

    print("👋 All servers stopped. Goodbye!")
    sys.exit(0)

def main():
    """Main function to start all servers"""
    print("🤝 AI Social Support Application with Authentication")
    print("=" * 60)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check Ollama (optional)
    ollama_running = check_ollama()
    if not ollama_running:
        print("⚠️ Ollama is not running. Chat features may not work properly.")
        print("   You can continue without it for basic functionality.")

    print("\n🚀 Starting all services...")
    print("=" * 60)

    # Start servers in threads
    threads = []
    for server in SERVERS:
        thread = threading.Thread(target=run_server, args=(server,))
        thread.daemon = True
        thread.start()
        threads.append(thread)
        time.sleep(2)  # Stagger startup

    # Wait for startup
    wait_for_startup()

    print("\n🎉 All services are running!")
    print("=" * 60)
    print("📍 Service URLs:")
    for server in SERVERS:
        print(f"   {server['name']}: {server['url']}")

    print("\n🌐 Open your browser and go to: http://localhost:8501")
    print("⚠️ Press Ctrl+C to stop all servers")
    print("=" * 60)

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()