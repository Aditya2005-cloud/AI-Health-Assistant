"""
Prompts package - Contains all AI system prompts.
"""

from prompts.gemini_diagnostic_prompt import GEMINI_SYSTEM_PROMPT
from prompts.groq_validation_prompt import GROQ_SYSTEM_PROMPT

__all__ = ["GEMINI_SYSTEM_PROMPT", "GROQ_SYSTEM_PROMPT"]
