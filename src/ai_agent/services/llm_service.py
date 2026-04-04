import json
import logging
from openai import AsyncOpenAI
from src.ai_agent.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Single client instance — reused across all calls
client = AsyncOpenAI(api_key=settings.openai_api_key)


class LLMService:
    """
    Wrapper around OpenAI API.
    All LLM calls go through here — never call OpenAI directly in routes.
    This makes it easy to swap models later (Claude, Gemini, local LLM).
    """

    def __init__(self):
        self.model = settings.openai_model
        self.client = client

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 1000
    ) -> str:
        """
        Basic completion — returns raw text response.
        temperature=0.1 for factual tasks (company research)
        temperature=0.8 for creative tasks (writing, brainstorming)
        """
        logger.info(f"Calling {self.model}...")

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )

        result = response.choices[0].message.content
        logger.info(f" LLM responded ({response.usage.total_tokens} tokens)")
        return result

    async def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1
    ) -> dict:
        """
        Forces LLM to return valid JSON.
        Uses OpenAI's response_format feature — never hallucinates JSON.
        This is how you get structured data from LLMs reliably.
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=1000,
            response_format={"type": "json_object"},   # ← forces JSON output
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )

        raw = response.choices[0].message.content
        logger.info(f" LLM JSON response ({response.usage.total_tokens} tokens)")

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {raw}")
            raise ValueError(f"LLM returned invalid JSON: {e}")