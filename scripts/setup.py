#!/usr/bin/env python3
"""
AI Social Support Application - Setup and Validation Script
===========================================================

This script helps set up the development environment and validates
all dependencies for the AI Social Support application.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
import json
import requests


class SetupValidator:
    """Validates and sets up the development environment"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.platform = platform.system().lower()
        self.errors = []
        self.warnings = []

    def log_error(self, message: str):
        """Log an error message"""
        self.errors.append(message)
        print(f"❌ ERROR: {message}")

    def log_warning(self, message: str):
        """Log a warning message"""
        self.warnings.append(message)
        print(f"⚠️  WARNING: {message}")

    def log_success(self, message: str):
        """Log a success message"""
        print(f"✅ {message}")

    def check_python_version(self):
        """Check Python version compatibility"""
        print("\n🐍 Checking Python version...")

        version = sys.version_info
        if version < (3, 9):
            self.log_error(f"Python 3.9+ required, found {version.major}.{version.minor}.{version.micro}")
            return False
        elif version >= (3, 13):
            self.log_warning(f"Python {version.major}.{version.minor} may have compatibility issues with some packages")

        self.log_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True

    def check_virtual_environment(self):
        """Check if virtual environment is active"""
        print("\n🏠 Checking virtual environment...")

        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            self.log_success("Virtual environment is active")
            return True
        else:
            self.log_warning("Virtual environment not detected - recommended for development")
            return True

    def check_ollama_installation(self):
        """Check Ollama installation and models"""
        print("\n🧠 Checking Ollama installation...")

        try:
            # Check if ollama command exists
            result = subprocess.run(['ollama', '--version'],
                                 capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.log_error("Ollama is not installed or not working")
                return False

            version = result.stdout.strip()
            self.log_success(f"Ollama installed: {version}")

            # Check if service is running
            try:
                response = requests.get('http://localhost:11434/api/tags', timeout=5)
                if response.status_code == 200:
                    self.log_success("Ollama service is running")

                    # Check available models
                    models = response.json().get('models', [])
                    model_names = [model['name'] for model in models]

                    recommended_models = ['qwen2:1.5b', 'llama3.2:3b', 'phi3:mini']
                    found_model = None

                    for model in recommended_models:
                        if model in model_names:
                            found_model = model
                            break

                    if found_model:
                        self.log_success(f"Recommended model found: {found_model}")
                    else:
                        self.log_warning("No recommended models found. Install with: ollama pull qwen2:1.5b")

                else:
                    self.log_warning("Ollama service not responding")

            except requests.exceptions.RequestException:
                self.log_warning("Ollama service not running. Start with: ollama serve")

            return True

        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.log_error("Ollama not installed. Install from: https://ollama.ai/install")
            return False

    def check_docker_installation(self):
        """Check Docker installation (optional)"""
        print("\n🐳 Checking Docker installation...")

        try:
            result = subprocess.run(['docker', '--version'],
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.log_success(f"Docker installed: {version}")

                # Check if docker-compose is available
                try:
                    result = subprocess.run(['docker-compose', '--version'],
                                         capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        self.log_success("docker-compose available")
                except FileNotFoundError:
                    self.log_warning("docker-compose not found (optional for databases)")

                return True
            else:
                self.log_warning("Docker installed but not working")
                return False

        except FileNotFoundError:
            self.log_warning("Docker not installed (optional for production databases)")
            return True

    def check_required_directories(self):
        """Check and create required directories"""
        print("\n📁 Checking directory structure...")

        required_dirs = [
            'backend',
            'frontend',
            'data',
            'data/temp',
            'data/uploads',
            'logs',
            'scripts'
        ]

        for dir_name in required_dirs:
            dir_path = self.base_dir / dir_name
            if dir_path.exists():
                self.log_success(f"Directory exists: {dir_name}")
            else:
                dir_path.mkdir(parents=True, exist_ok=True)
                self.log_success(f"Created directory: {dir_name}")

        return True

    def check_environment_file(self):
        """Check .env file"""
        print("\n⚙️  Checking environment configuration...")

        env_file = self.base_dir / '.env'
        env_example = self.base_dir / '.env.example'

        if env_file.exists():
            self.log_success(".env file exists")
            return True
        elif env_example.exists():
            self.log_warning(".env file not found, but .env.example exists")
            print("   Copy .env.example to .env and update values")
            return True
        else:
            self.log_warning("No environment configuration found")
            self.create_basic_env_file()
            return True

    def create_basic_env_file(self):
        """Create a basic .env file"""
        env_content = """# AI Social Support Application Configuration

# Ollama LLM Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2:1.5b

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_PORT=8501
LLM_SERVICE_PORT=8001

# Database Configuration (for production)
POSTGRES_URL=postgresql://postgres:postgres123@localhost:5432/ai_social_support
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://:redis123@localhost:6379

# Application Settings
MAX_FILE_SIZE=10485760
LOG_LEVEL=INFO
DEBUG=true

# Security (change in production)
SECRET_KEY=your-secret-key-here
"""

        env_file = self.base_dir / '.env'
        with open(env_file, 'w') as f:
            f.write(env_content)

        self.log_success("Created basic .env file")

    def check_python_dependencies(self):
        """Check if required Python packages are installed"""
        print("\n📦 Checking Python dependencies...")

        required_packages = [
            'fastapi',
            'streamlit',
            'uvicorn',
            'langchain',
            'ollama',
            'requests',
            'pydantic',
            'sqlalchemy'
        ]

        missing_packages = []

        for package in required_packages:
            try:
                __import__(package)
                self.log_success(f"Package installed: {package}")
            except ImportError:
                missing_packages.append(package)
                self.log_warning(f"Package missing: {package}")

        if missing_packages:
            print(f"\n💡 Install missing packages with:")
            print(f"   pip install {' '.join(missing_packages)}")
            print(f"   OR: pip install -r requirements.txt")

        return len(missing_packages) == 0

    def check_port_availability(self):
        """Check if required ports are available"""
        print("\n🔌 Checking port availability...")

        required_ports = {
            8000: "FastAPI Backend",
            8001: "LLM Service",
            8501: "Streamlit Frontend",
            11434: "Ollama API"
        }

        for port, service in required_ports.items():
            if self.is_port_available(port):
                self.log_success(f"Port {port} available for {service}")
            else:
                self.log_warning(f"Port {port} in use (needed for {service})")

        return True

    def is_port_available(self, port: int) -> bool:
        """Check if a port is available"""
        import socket

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                return result != 0
        except Exception:
            return True

    def run_validation(self):
        """Run complete validation"""
        print("🚀 AI Social Support Application - Environment Setup Validator")
        print("=" * 60)

        checks = [
            self.check_python_version,
            self.check_virtual_environment,
            self.check_ollama_installation,
            self.check_docker_installation,
            self.check_required_directories,
            self.check_environment_file,
            self.check_python_dependencies,
            self.check_port_availability
        ]

        for check in checks:
            try:
                check()
            except Exception as e:
                self.log_error(f"Validation check failed: {e}")

        # Summary
        print("\n" + "=" * 60)
        print("📋 VALIDATION SUMMARY")
        print("=" * 60)

        if self.errors:
            print(f"❌ {len(self.errors)} Error(s):")
            for error in self.errors:
                print(f"   • {error}")

        if self.warnings:
            print(f"⚠️  {len(self.warnings)} Warning(s):")
            for warning in self.warnings:
                print(f"   • {warning}")

        if not self.errors and not self.warnings:
            print("✅ All checks passed! Environment is ready.")
        elif not self.errors:
            print("⚠️  Environment is mostly ready, but check warnings above.")
        else:
            print("❌ Environment has issues that need to be resolved.")

        print("\n💡 Next steps:")
        if not self.errors:
            print("   1. Run: python run_local.py")
            print("   2. Open: http://localhost:8501")
        else:
            print("   1. Fix the errors listed above")
            print("   2. Run this script again to validate")

        return len(self.errors) == 0


def main():
    """Main entry point"""
    validator = SetupValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()