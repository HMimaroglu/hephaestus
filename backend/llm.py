import asyncio
import logging
from typing import Optional, Dict, Any
import httpx
from backend.settings import settings

logger = logging.getLogger(__name__)


class LLMAdapter:

    def __init__(self):
        self.backend = settings.llm_backend
        self.model = settings.llm_model
        self.host = settings.llm_host
        self.timeout = settings.llm_timeout

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        if self.backend == "ollama":
            return await self._ollama_generate(prompt, system_prompt, temperature, max_tokens)
        elif self.backend == "llama_cpp":
            return await self._llama_cpp_generate(prompt, system_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported LLM backend: {self.backend}")

    async def _ollama_generate(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        url = f"{self.host}/api/generate"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.TimeoutException:
            logger.error(f"LLM request timed out after {self.timeout}s")
            raise
        except httpx.HTTPError as e:
            logger.error(f"LLM request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in LLM generation: {e}")
            raise

    async def _llama_cpp_generate(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        url = f"{self.host}/completion"

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "prompt": full_prompt,
            "temperature": temperature,
            "n_predict": max_tokens,
            "stop": ["</s>", "User:", "Assistant:"]
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("content", "")
        except httpx.TimeoutException:
            logger.error(f"LLM request timed out after {self.timeout}s")
            raise
        except httpx.HTTPError as e:
            logger.error(f"LLM request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in LLM generation: {e}")
            raise

    async def health_check(self) -> bool:
        try:
            if self.backend == "ollama":
                url = f"{self.host}/api/tags"
            else:
                url = f"{self.host}/health"

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False


llm_adapter = LLMAdapter()
