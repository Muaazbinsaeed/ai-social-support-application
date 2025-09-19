# Ollama Setup Guide for AI Social Support Application

This guide will help you install and configure Ollama with the appropriate models for the AI Social Support Application.

## What is Ollama?

Ollama is a tool that allows you to run Large Language Models (LLMs) locally on your machine without requiring a GPU. It's perfect for this application as it provides privacy, cost-effectiveness, and offline capabilities.

## Installation

### Step 1: Install Ollama

#### macOS
```bash
# Download and install from the official website
curl -fsSL https://ollama.ai/install.sh | sh

# Or using Homebrew
brew install ollama
```

#### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Windows
Download the installer from [https://ollama.ai/download](https://ollama.ai/download)

### Step 2: Verify Installation

```bash
ollama --version
```

### Step 3: Start Ollama Service

```bash
# Start Ollama service (will run on http://localhost:11434)
ollama serve
```

## Recommended Models

For the AI Social Support Application, we recommend the following models optimized for CPU usage:

### Primary Model: Llama 3.2 3B (Recommended)

```bash
# Download and install Llama 3.2 3B model (~2GB)
ollama pull llama3.2:3b
```

**Why Llama 3.2 3B?**
- Optimized for CPU inference
- Good performance for text analysis and reasoning
- Relatively small size (2GB)
- Strong instruction following capabilities
- Good performance for document analysis tasks

### Alternative Models

#### Option 1: Mistral 7B (If you have more RAM)
```bash
# Download Mistral 7B model (~4GB)
ollama pull mistral:7b
```

#### Option 2: Phi-3 Mini (Fastest, smallest)
```bash
# Download Phi-3 Mini model (~2GB)
ollama pull phi3:mini
```

#### Option 3: Code Llama (For code analysis tasks)
```bash
# Download Code Llama model
ollama pull codellama:7b
```

## Model Configuration

### Test Your Model

After installing a model, test it:

```bash
# Test the model
ollama run llama3.2:3b "Hello, can you help me analyze a social support application?"
```

### Performance Optimization

#### CPU Optimization
```bash
# Set environment variables for better CPU performance
export OLLAMA_NUM_PARALLEL=4
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_FLASH_ATTENTION=1
```

#### Memory Settings
```bash
# For systems with limited RAM (8GB or less)
export OLLAMA_MAX_QUEUE=2

# For systems with more RAM (16GB+)
export OLLAMA_MAX_QUEUE=4
```

## Application Configuration

### Update .env File

Create or update your `.env` file with the Ollama configuration:

```env
# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b

# Alternative model options:
# OLLAMA_MODEL=mistral:7b
# OLLAMA_MODEL=phi3:mini
# OLLAMA_MODEL=codellama:7b
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Model Download Fails
```bash
# Check your internet connection and try again
ollama pull llama3.2:3b --verbose
```

#### 2. Service Won't Start
```bash
# Check if port 11434 is available
lsof -i :11434

# Kill any existing process
killall ollama

# Restart service
ollama serve
```

#### 3. Model Running Too Slowly
- Try a smaller model (phi3:mini)
- Reduce concurrent requests in application
- Increase system RAM if possible
- Close other applications to free up memory

#### 4. Out of Memory Errors
```bash
# Use a smaller model
ollama pull phi3:mini

# Update your .env file
OLLAMA_MODEL=phi3:mini
```

### Performance Monitoring

Monitor Ollama performance:

```bash
# Check running models
ollama ps

# Check available models
ollama list

# Monitor system resources
htop
```

## Model Comparison

| Model | Size | RAM Required | Speed | Quality | Best For |
|-------|------|-------------|--------|---------|----------|
| Phi-3 Mini | 2GB | 4GB | Fast | Good | Quick responses |
| Llama 3.2 3B | 2GB | 6GB | Medium | Very Good | **Recommended** |
| Mistral 7B | 4GB | 8GB | Slower | Excellent | Complex analysis |
| Code Llama 7B | 4GB | 8GB | Slower | Excellent | Code tasks |

## Integration with Application

### Backend Integration

The application automatically connects to Ollama using the configuration in your `.env` file. The integration points are:

1. **Data Extraction Agent**: Uses LLM for extracting structured data from documents
2. **Validation Agent**: Uses LLM for validating data consistency
3. **Eligibility Agent**: Uses LLM for complex eligibility reasoning
4. **Decision Agent**: Uses LLM for generating final recommendations

### API Endpoints

Test the integration:

```bash
# Test if Ollama is accessible from the application
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "Test connection",
  "stream": false
}'
```

## Advanced Configuration

### Custom Model Parameters

You can customize model behavior by creating a Modelfile:

```bash
# Create a custom configuration
cat > social_support_model << EOF
FROM llama3.2:3b

# Set custom parameters
PARAMETER temperature 0.1
PARAMETER top_p 0.9
PARAMETER top_k 40

# Set system prompt for social support context
SYSTEM You are an AI assistant specialized in social support applications. You analyze documents, validate information, and make recommendations based on eligibility criteria.
EOF

# Create the custom model
ollama create social-support -f social_support_model
```

Then update your `.env`:
```env
OLLAMA_MODEL=social-support
```

### Multiple Model Setup

For production environments, you might want to use different models for different tasks:

```env
# Different models for different agents
OLLAMA_EXTRACTION_MODEL=llama3.2:3b
OLLAMA_VALIDATION_MODEL=mistral:7b
OLLAMA_DECISION_MODEL=llama3.2:3b
```

## Security Considerations

### Local Deployment Benefits
- **Privacy**: All data stays on your local machine
- **Compliance**: No data sent to external services
- **Cost**: No API charges
- **Offline**: Works without internet connection

### Network Security
```bash
# Bind Ollama to localhost only (default)
ollama serve --host 127.0.0.1:11434

# For production, consider using authentication
# (Note: Ollama doesn't have built-in auth, use reverse proxy)
```

## Next Steps

1. **Install Ollama** following the steps above
2. **Download the recommended model** (llama3.2:3b)
3. **Test the installation** with the test command
4. **Update your .env file** with the correct configuration
5. **Start the application** and verify integration

## Support

If you encounter issues:

1. Check the [Ollama documentation](https://ollama.ai/docs)
2. Review the application logs for Ollama connection errors
3. Ensure you have sufficient RAM for your chosen model
4. Try a smaller model if performance is poor

## Performance Tips

1. **Close unnecessary applications** to free up RAM
2. **Use SSD storage** for better model loading times
3. **Adjust model parameters** for your use case
4. **Monitor system resources** during operation
5. **Consider model size vs. quality tradeoffs**

---

**Note**: The AI Social Support Application is designed to work efficiently with CPU-only inference. You don't need a GPU to run this system effectively.