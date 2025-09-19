#!/usr/bin/env python3
"""
AI Social Support Application - Local Development Runner
========================================================

This script provides a comprehensive way to run the AI Social Support application
locally with proper service management, health checks, and error handling.

Usage:
    python run_local.py                    # Run all services
    python run_local.py --backend-only     # Run only backend services
    python run_local.py --frontend-only    # Run only frontend
    python run_local.py --check-health     # Check service health
    python run_local.py --stop-all         # Stop all services
"""

import os
import sys
import subprocess
import time
import signal
import json
import threading
import requests
from pathlib import Path
from typing import Dict, List, Optional
import argparse


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class ServiceManager:
    """Manages all services for the AI Social Support application"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.services = {}
        self.running = True

        # Service configurations
        self.service_configs = {
            'ollama': {
                'name': 'Ollama LLM Service',
                'port': 11434,
                'health_endpoint': 'http://localhost:11434/api/tags',
                'start_command': None,  # Ollama should be started manually
                'required': True
            },
            'backend': {
                'name': 'FastAPI Backend',
                'port': 8000,
                'health_endpoint': 'http://localhost:8000/health',
                'start_command': [
                    sys.executable, '-m', 'uvicorn',
                    'backend.api.main:app',
                    '--host', '0.0.0.0',
                    '--port', '8000',
                    '--reload'
                ],
                'cwd': self.base_dir,
                'required': True
            },
            'chatbot': {
                'name': 'LLM Chatbot Service',
                'port': 8001,
                'health_endpoint': 'http://localhost:8001/health',
                'start_command': [
                    sys.executable, 'backend/services/llm_service.py'
                ],
                'cwd': self.base_dir,
                'required': False
            },
            'frontend': {
                'name': 'Streamlit Frontend',
                'port': 8501,
                'health_endpoint': 'http://localhost:8501/_stcore/health',
                'start_command': [
                    'streamlit', 'run', 'frontend/app.py',
                    '--server.port', '8501',
                    '--server.address', '0.0.0.0'
                ],
                'cwd': self.base_dir,
                'required': True
            }
        }

    def print_banner(self):
        """Print application banner"""
        banner = f"""
{Colors.HEADER}{'='*60}
🤖 AI Social Support Application - Local Runner
{'='*60}{Colors.ENDC}

{Colors.OKBLUE}Version:{Colors.ENDC} MVP (2025-09-19)
{Colors.OKBLUE}Platform:{Colors.ENDC} Local Development
{Colors.OKBLUE}LLM Model:{Colors.ENDC} qwen2:1.5b (Ollama)

{Colors.OKCYAN}Services to start:{Colors.ENDC}
"""
        print(banner)

        for service_id, config in self.service_configs.items():
            status = "🔄" if config['required'] else "⚡"
            print(f"  {status} {config['name']} (Port {config['port']})")

        print(f"\n{Colors.WARNING}Press Ctrl+C to stop all services{Colors.ENDC}\n")

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met"""
        print(f"{Colors.OKBLUE}Checking prerequisites...{Colors.ENDC}")

        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 9):
            print(f"{Colors.FAIL}❌ Python 3.9+ required, found {python_version.major}.{python_version.minor}{Colors.ENDC}")
            return False
        print(f"{Colors.OKGREEN}✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}{Colors.ENDC}")

        # Check virtual environment
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            print(f"{Colors.OKGREEN}✅ Virtual environment active{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}⚠️  Virtual environment not detected{Colors.ENDC}")

        # Check required directories
        required_dirs = ['backend', 'frontend', 'data']
        for dir_name in required_dirs:
            dir_path = self.base_dir / dir_name
            if dir_path.exists():
                print(f"{Colors.OKGREEN}✅ Directory: {dir_name}{Colors.ENDC}")
            else:
                print(f"{Colors.WARNING}⚠️  Creating directory: {dir_name}{Colors.ENDC}")
                dir_path.mkdir(parents=True, exist_ok=True)

        # Check .env file
        env_file = self.base_dir / '.env'
        if env_file.exists():
            print(f"{Colors.OKGREEN}✅ Environment configuration found{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}⚠️  .env file not found, using defaults{Colors.ENDC}")

        # Check Ollama
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"{Colors.OKGREEN}✅ Ollama installed and accessible{Colors.ENDC}")
                if 'qwen2:1.5b' in result.stdout:
                    print(f"{Colors.OKGREEN}✅ qwen2:1.5b model available{Colors.ENDC}")
                else:
                    print(f"{Colors.WARNING}⚠️  qwen2:1.5b model not found, will use available model{Colors.ENDC}")
            else:
                print(f"{Colors.FAIL}❌ Ollama not working properly{Colors.ENDC}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print(f"{Colors.FAIL}❌ Ollama not installed or not in PATH{Colors.ENDC}")
            print(f"{Colors.OKCYAN}Install with: curl -fsSL https://ollama.ai/install.sh | sh{Colors.ENDC}")
            return False

        return True

    def check_service_health(self, service_id: str, timeout: int = 5) -> bool:
        """Check if a service is healthy"""
        config = self.service_configs[service_id]
        try:
            response = requests.get(config['health_endpoint'], timeout=timeout)
            return response.status_code in [200, 404]  # 404 is OK for some services
        except requests.exceptions.RequestException:
            return False

    def wait_for_service(self, service_id: str, timeout: int = 30) -> bool:
        """Wait for a service to become healthy"""
        config = self.service_configs[service_id]
        print(f"  Waiting for {config['name']}...")

        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.check_service_health(service_id):
                print(f"  {Colors.OKGREEN}✅ {config['name']} is ready{Colors.ENDC}")
                return True
            time.sleep(1)

        print(f"  {Colors.FAIL}❌ {config['name']} failed to start within {timeout}s{Colors.ENDC}")
        return False

    def start_service(self, service_id: str) -> Optional[subprocess.Popen]:
        """Start a single service"""
        config = self.service_configs[service_id]

        if service_id == 'ollama':
            # Check if Ollama is already running
            if self.check_service_health('ollama'):
                print(f"  {Colors.OKGREEN}✅ {config['name']} already running{Colors.ENDC}")
                return None
            else:
                print(f"  {Colors.FAIL}❌ Ollama not running. Please start with: ollama serve{Colors.ENDC}")
                return None

        print(f"  🚀 Starting {config['name']}...")

        try:
            # Set up environment
            env = os.environ.copy()
            env['PYTHONPATH'] = str(self.base_dir)

            process = subprocess.Popen(
                config['start_command'],
                cwd=config.get('cwd', self.base_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Give the service a moment to start
            time.sleep(2)

            if process.poll() is None:
                return process
            else:
                stdout, stderr = process.communicate()
                print(f"  {Colors.FAIL}❌ {config['name']} failed to start{Colors.ENDC}")
                if stderr:
                    print(f"  Error: {stderr[:200]}...")
                return None

        except Exception as e:
            print(f"  {Colors.FAIL}❌ Failed to start {config['name']}: {e}{Colors.ENDC}")
            return None

    def start_all_services(self, backend_only: bool = False, frontend_only: bool = False):
        """Start all required services"""
        print(f"{Colors.OKBLUE}Starting services...{Colors.ENDC}")

        # Determine which services to start
        services_to_start = []
        if frontend_only:
            services_to_start = ['ollama', 'frontend']
        elif backend_only:
            services_to_start = ['ollama', 'backend', 'chatbot']
        else:
            services_to_start = list(self.service_configs.keys())

        # Start services in order
        for service_id in services_to_start:
            process = self.start_service(service_id)
            if process:
                self.services[service_id] = process

        # Wait for services to be ready
        print(f"\n{Colors.OKBLUE}Waiting for services to be ready...{Colors.ENDC}")
        all_ready = True

        for service_id in services_to_start:
            if service_id in self.services or service_id == 'ollama':
                if not self.wait_for_service(service_id):
                    all_ready = False

        if all_ready:
            self.print_service_urls()
            return True
        else:
            print(f"\n{Colors.FAIL}❌ Some services failed to start properly{Colors.ENDC}")
            return False

    def print_service_urls(self):
        """Print service URLs"""
        print(f"\n{Colors.OKGREEN}{'='*60}")
        print("🚀 All services are ready!")
        print("="*60)
        print(f"🌐 Frontend:           http://localhost:8501")
        print(f"📡 Backend API:        http://localhost:8000")
        print(f"📚 API Documentation:  http://localhost:8000/docs")
        print(f"🤖 LLM Service:        http://localhost:8001")
        print(f"🧠 Ollama API:         http://localhost:11434")
        print("="*60)
        print(f"💡 Open http://localhost:8501 to use the application")
        print(f"📖 Visit http://localhost:8000/docs for API documentation")
        print(f"⏹️  Press Ctrl+C to stop all services{Colors.ENDC}\n")

    def stop_all_services(self):
        """Stop all running services"""
        print(f"\n{Colors.WARNING}Stopping all services...{Colors.ENDC}")

        for service_id, process in self.services.items():
            config = self.service_configs[service_id]
            print(f"  🛑 Stopping {config['name']}...")

            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"  ⚡ Force killing {config['name']}...")
                process.kill()
                process.wait()
            except Exception as e:
                print(f"  ⚠️  Error stopping {config['name']}: {e}")

        print(f"{Colors.OKGREEN}✅ All services stopped{Colors.ENDC}")

    def check_all_health(self):
        """Check health of all services"""
        print(f"{Colors.OKBLUE}Checking service health...{Colors.ENDC}")

        for service_id, config in self.service_configs.items():
            if self.check_service_health(service_id):
                print(f"  {Colors.OKGREEN}✅ {config['name']} (Port {config['port']}){Colors.ENDC}")
            else:
                print(f"  {Colors.FAIL}❌ {config['name']} (Port {config['port']}){Colors.ENDC}")

    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n{Colors.WARNING}Received interrupt signal...{Colors.ENDC}")
        self.running = False
        self.stop_all_services()
        sys.exit(0)

    def run(self, backend_only: bool = False, frontend_only: bool = False):
        """Main run method"""
        # Set up signal handler
        signal.signal(signal.SIGINT, self.signal_handler)

        self.print_banner()

        if not self.check_prerequisites():
            print(f"\n{Colors.FAIL}❌ Prerequisites not met. Please fix the issues above.{Colors.ENDC}")
            return False

        if self.start_all_services(backend_only, frontend_only):
            # Keep the main thread alive
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                self.stop_all_services()
            return True
        else:
            self.stop_all_services()
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='AI Social Support Application Local Runner')
    parser.add_argument('--backend-only', action='store_true', help='Run only backend services')
    parser.add_argument('--frontend-only', action='store_true', help='Run only frontend')
    parser.add_argument('--check-health', action='store_true', help='Check service health')
    parser.add_argument('--stop-all', action='store_true', help='Stop all services')

    args = parser.parse_args()

    manager = ServiceManager()

    if args.check_health:
        manager.check_all_health()
    elif args.stop_all:
        manager.stop_all_services()
    else:
        success = manager.run(
            backend_only=args.backend_only,
            frontend_only=args.frontend_only
        )
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()