"""LLM structured extraction — fallback only; never pass/fail.

LLM_PROVIDER=gemini|openai|none (default gemini adapter when AI enabled;
none skips LLM entirely and uses OCR + regex only).
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.core.config import get_settings

logger = logging.getLogger("praman.llm_extractor")


class LLMExtractor(ABC):
    name: str = "llm"

    @abstractmethod
    def extract(self, text: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return dict of field_name -> value. Never decides pass/fail."""


class NullLLMExtractor(LLMExtractor):
    name = "llm_none"

    def extract(self, text: str, schema: dict[str, Any]) -> dict[str, Any]:
        logger.info("LLM_PROVIDER=none — skipping LLM; OCR/regex only")
        return {}


class GeminiLLMExtractor(LLMExtractor):
    name = "llm_gemini"

    def extract(self, text: str, schema: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        api_key = settings.llm_api_key
        if not api_key:
            logger.warning("Gemini selected but LLM_API_KEY empty — returning no fields")
            return {}
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError:
            logger.warning("google-generativeai not installed — degrade gracefully")
            return {}
        genai.configure(api_key=api_key)
        model_name = settings.llm_model or "gemini-1.5-flash"
        model = genai.GenerativeModel(model_name)
        prompt = (
            "Extract fields as strict JSON only (no markdown). "
            f"Schema keys: {list((schema.get('properties') or schema).keys())}. "
            f"Text:\n{text[:12000]}"
        )
        try:
            resp = model.generate_content(prompt)
            return _parse_json_object(getattr(resp, "text", "") or "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini extraction failed: %s", exc)
            return {}


class OpenAILLMExtractor(LLMExtractor):
    name = "llm_openai"

    def extract(self, text: str, schema: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        api_key = settings.llm_api_key
        if not api_key:
            logger.warning("OpenAI selected but LLM_API_KEY empty — returning no fields")
            return {}
        try:
            from openai import OpenAI  # type: ignore
        except ImportError:
            logger.warning("openai package not installed — degrade gracefully")
            return {}
        client = OpenAI(api_key=api_key)
        model_name = settings.llm_model or "gpt-4o-mini"
        prompt = (
            "Extract fields as strict JSON only (no markdown). "
            f"Schema keys: {list((schema.get('properties') or schema).keys())}. "
            f"Text:\n{text[:12000]}"
        )
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or "{}"
            return _parse_json_object(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI extraction failed: %s", exc)
            return {}


def _parse_json_object(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def get_llm_extractor(provider: Optional[str] = None) -> LLMExtractor:
    settings = get_settings()
    prov = (provider or settings.llm_provider or "none").strip().lower()
    if prov in ("", "none", "null", "off"):
        return NullLLMExtractor()
    if prov in ("gemini", "google", "google-generativeai"):
        return GeminiLLMExtractor()
    if prov in ("openai", "gpt"):
        return OpenAILLMExtractor()
    logger.warning("Unknown LLM_PROVIDER=%s — using none", prov)
    return NullLLMExtractor()
