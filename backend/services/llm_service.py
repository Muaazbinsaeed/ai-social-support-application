import httpx
import json
import asyncio
from typing import Dict, Any, Optional, List
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    """
    Service for interacting with Ollama LLM for intelligent chatbot responses
    """

    def __init__(self):
        self.base_url = settings.ollama_host
        self.model = settings.ollama_model
        self.timeout = 60.0

        # System prompt for the social support assistant
        self.system_prompt = """You are an AI Assistant for the UAE Social Support Application System. You are knowledgeable, helpful, and professional. Your role is to assist citizens and residents with:

1. Social support application process
2. Document requirements and upload procedures
3. Eligibility criteria and assessment factors
4. System features and capabilities
5. Processing timelines and status updates
6. Security and privacy information
7. General guidance and FAQs

Key Information:
- This is an AI-powered system that processes applications in 2-5 minutes vs traditional 5-20 working days
- Uses local LLM (no external data sharing) for privacy
- Supports Arabic and English documents with OCR
- Processes Emirates ID, bank statements, income proof, family certificates, credit reports
- Eligibility: UAE residency, income below AED 4,000/month, genuine financial need
- Two main programs: Financial Support and Economic Enablement
- Multi-agent system with data extraction, validation, eligibility, and decision agents

Always be:
- Professional and empathetic
- Clear and informative
- Supportive and encouraging
- Accurate about system capabilities
- Respectful of user privacy concerns

Respond in a helpful, concise manner. Use emojis sparingly for clarity. If you don't know something specific, acknowledge it and suggest where they might find the information.
"""

    async def _make_request(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Make a request to Ollama API"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "system": system_prompt or self.system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "top_k": 40,
                        "num_predict": 500
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
                    logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                    return None

        except httpx.TimeoutException:
            logger.error("Ollama API timeout")
            return None
        except Exception as e:
            logger.error(f"Ollama API error: {str(e)}")
            return None

    async def get_chat_response(self, user_message: str, context: Optional[Dict] = None) -> str:
        """Get intelligent chatbot response using LLM"""

        # Add context if available
        prompt = user_message
        if context:
            if context.get("application_id"):
                prompt = f"User has application ID {context['application_id']}. {prompt}"
            if context.get("has_documents"):
                prompt = f"User has uploaded documents. {prompt}"
            if context.get("processing_status"):
                prompt = f"User's application status is {context['processing_status']}. {prompt}"

        # Try to get LLM response
        llm_response = await self._make_request(prompt)

        if llm_response:
            return llm_response
        else:
            # Fallback to rule-based response if LLM fails
            return self._get_fallback_response(user_message)

    def _get_fallback_response(self, user_message: str) -> str:
        """Fallback rule-based response if LLM is unavailable"""
        user_lower = user_message.lower()

        if any(word in user_lower for word in ["hello", "hi", "hey"]):
            return "👋 Hello! I'm your AI Social Support Assistant. I'm here to help you with your application process. How can I assist you today?"

        elif "document" in user_lower:
            return "📄 For document requirements and upload instructions, I can help! What specific information do you need about documents?"

        elif "eligibility" in user_lower:
            return "✅ I can help you understand the eligibility criteria. The main requirements include UAE residency and monthly income below AED 4,000. Would you like more details?"

        elif "status" in user_lower:
            return "📊 I can help you check your application status. Have you submitted an application yet?"

        elif "help" in user_lower:
            return "🤝 I'm here to help! I can assist with applications, documents, eligibility, and general questions about the social support system."

        else:
            return "I'm here to help with your social support application. Could you please tell me what specific information you're looking for? I can assist with applications, documents, eligibility, or general questions."

    async def check_health(self) -> bool:
        """Check if Ollama service is available"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False

# Global service instance
llm_service = LLMService()