from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import httpx
import json
import os

# Simple settings without complex imports
class SimpleSettings:
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2:1.5b")
        self.api_host = os.getenv("API_HOST", "0.0.0.0")

settings = SimpleSettings()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Social Support Chat API",
    description="LLM-powered chatbot for social support applications",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimpleLLMService:
    """Simplified LLM service for chatbot"""

    def __init__(self):
        self.base_url = settings.ollama_host
        self.model = settings.ollama_model
        self.timeout = 15.0  # Increased timeout for better reliability

        self.system_prompt = """You are a UAE Social Support Assistant. Give short, helpful answers.

I help with:
• Application process & eligibility
• Document requirements
• Financial support programs

Quick facts:
• Eligibility: UAE residency, income <AED 4,000/month
• Docs needed: Emirates ID, bank statements, income proof
• Fast AI processing: 2-5 minutes

Keep responses under 50 words. Use emojis and be friendly."""

    def _is_programming_request(self, prompt: str) -> bool:
        """Detect if the request is about programming/coding"""
        prompt_lower = prompt.lower()

        # Programming keywords and phrases
        programming_keywords = [
            "write code", "python code", "write python", "python print", "print code",
            "javascript", "html", "css", "sql", "java", "c++", "c#", ".net",
            "programming", "coding", "script", "function", "variable", "loop",
            "array", "list", "dictionary", "api call", "database query",
            "for loop", "while loop", "if statement", "else statement",
            "import", "from ", "def ", "class ", "return ", "print(",
            "console.log", "alert(", "document.", "window.", "var ", "let ",
            "const ", "function(", "=>", "lambda", "exec", "eval"
        ]

        # Programming file extensions
        file_extensions = [
            ".py", ".js", ".html", ".css", ".sql", ".java", ".cpp", ".cs",
            ".php", ".rb", ".go", ".rs", ".ts", ".jsx", ".tsx", ".vue"
        ]

        # Check for programming keywords
        for keyword in programming_keywords:
            if keyword in prompt_lower:
                return True

        # Check for file extensions
        for ext in file_extensions:
            if ext in prompt_lower:
                return True

        # Check for code-like patterns
        if any(pattern in prompt_lower for pattern in ["write me", "create a", "build a", "make a"]):
            if any(code_word in prompt_lower for code_word in ["code", "script", "program", "function", "app", "website"]):
                return True

        return False

    async def get_response(self, prompt: str, context: Optional[Dict] = None) -> str:
        """Get response from Ollama"""
        try:
            # Quick responses for very simple greetings only
            prompt_lower = prompt.lower().strip()
            if prompt_lower in ["hi", "hello", "hey"]:
                return "👋 Hello! I'm your AI Social Support Assistant. I can help with applications, documents, and eligibility. What would you like to know?"

            # Check if this is a programming request
            if self._is_programming_request(prompt):
                return "🚫 I'm specifically designed to help with UAE social support applications and services. I can assist with application processes, document requirements, eligibility criteria, and financial support programs. How can I help you with your social support needs?"

            # For more complex questions, always use LLM (removed instant responses for "what can you do" etc.)

            # Add context if available
            enhanced_prompt = prompt
            if context:
                if context.get("application_id"):
                    enhanced_prompt = f"User has application ID {context['application_id']}. {prompt}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": self.model,
                    "prompt": enhanced_prompt,
                    "system": self.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.7,
                        "top_k": 10,
                        "num_predict": 100
                    }
                }

                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "").strip()
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    return self._fallback_response(prompt)

        except Exception as e:
            logger.error(f"Ollama error: {str(e)}", exc_info=True)
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """Simple fallback responses"""
        prompt_lower = prompt.lower()

        if any(word in prompt_lower for word in ["hello", "hi", "hey"]):
            return "👋 Hello! I'm your AI Social Support Assistant. I'm here to help you with your application process."

        elif "document" in prompt_lower:
            return "📄 For documents, you'll need Emirates ID, bank statements (last 3 months), income proof, and family composition certificate. What specific document question do you have?"

        elif "eligibility" in prompt_lower:
            return "✅ Basic eligibility: UAE residency, monthly income below AED 4,000, valid Emirates ID, and genuine financial need. Would you like more details?"

        elif "process" in prompt_lower or "how" in prompt_lower:
            return "⚙️ The process: 1) Submit application form, 2) Upload documents, 3) AI processing (2-5 minutes), 4) Get decision. What part would you like to know more about?"

        else:
            return "I'm here to help with your social support application! I can assist with applications, documents, eligibility, and general questions. What would you like to know?"

    async def check_health(self) -> bool:
        """Check Ollama availability"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False

# Global service instance
llm_service = SimpleLLMService()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "AI Social Support Chat API",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/chat/message")
async def chat_message(
    message: str,
    application_id: Optional[int] = None
):
    """Send a message to the AI chatbot and get an intelligent response"""
    try:
        # Build context
        context = {}
        if application_id:
            context["application_id"] = application_id

        # Get LLM response
        response = await llm_service.get_response(message, context)

        return {
            "message": message,
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "context_used": bool(context),
            "service": "Ollama"
        }

    except Exception as e:
        logger.error(f"Chat message failed: {str(e)}")
        return {
            "message": message,
            "response": "I'm here to help with your social support application. Could you please rephrase your question?",
            "timestamp": datetime.now().isoformat(),
            "context_used": False,
            "fallback": True,
            "service": "Fallback"
        }

@app.get("/chat/health")
async def chat_health():
    """Check if the LLM service is available"""
    try:
        is_healthy = await llm_service.check_health()
        return {
            "llm_available": is_healthy,
            "service": "Ollama" if is_healthy else "Fallback",
            "model": settings.ollama_model,
            "status": "healthy" if is_healthy else "degraded",
            "ollama_host": settings.ollama_host
        }
    except Exception as e:
        logger.error(f"Chat health check failed: {str(e)}")
        return {
            "llm_available": False,
            "service": "Fallback",
            "model": "rule-based",
            "status": "degraded",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=8001,  # Different port to avoid conflicts
        reload=False
    )