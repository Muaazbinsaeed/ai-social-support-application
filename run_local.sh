#!/bin/bash
# AI Social Support Application - Unix/Linux Startup Script
# =========================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "========================================"
echo "🤖 AI Social Support Application"
echo "Unix/Linux Local Runner"
echo "========================================"
echo -e "${NC}"

# Function to print colored messages
print_error() {
    echo -e "${RED}❌ ERROR: $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        print_error "Python is not installed or not in PATH"
        echo "Please install Python 3.9+ from https://python.org"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    print_error "Python 3.9+ required, found $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION found"

# Check if we're in the right directory
if [ ! -f "run_local.py" ]; then
    print_error "run_local.py not found"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Check if virtual environment is recommended
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "Virtual environment not detected"
    echo "Consider activating a virtual environment first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo ""
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Setup cancelled"
        exit 0
    fi
fi

# Make the Python script executable if needed
if [ ! -x "run_local.py" ]; then
    chmod +x run_local.py
fi

# Function to handle cleanup on exit
cleanup() {
    echo ""
    print_info "Cleaning up..."
    # Kill any background processes if needed
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Run the Python script with all arguments
print_info "Starting AI Social Support Application..."
echo ""

$PYTHON_CMD run_local.py "$@"

# Check exit code
if [ $? -ne 0 ]; then
    echo ""
    print_error "Application failed to start"
    echo "Check the error messages above"
    exit 1
fi

print_info "Application stopped successfully"