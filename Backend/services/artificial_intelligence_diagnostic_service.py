"""
AI Service Module - Handles communication with Gemini and Groq APIs.
Implements the dual-AI pipeline: Gemini (Medical Analyst) -> Groq (Senior Doctor Validator).
Includes a resilient fallback to Groq if Gemini API fails (e.g., 429 rate limit or quota exceeded).
Supports both the new google-genai SDK and the legacy google-generativeai SDK dynamically.
"""

import json
import logging
import re
from groq import Groq
from config import Config
from prompts import GEMINI_SYSTEM_PROMPT, GROQ_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Dynamic SDK Resolution to prevent startup crashes in misconfigured environments
HAS_NEW_GENAI = False
HAS_LEGACY_GENAI = False

try:
    from google import genai
    from google.genai import types
    HAS_NEW_GENAI = True
    logger.info("[AI Service] Successfully imported new google-genai SDK.")
except ImportError:
    try:
        import google.generativeai as legacy_genai
        HAS_LEGACY_GENAI = True
        logger.info("[AI Service] Falling back to legacy google-generativeai SDK wrapper.")
    except ImportError:
        logger.warning("[AI Service] No Google GenAI SDK found. Gemini will bypass to Groq fallback.")


def _extract_json(text):
    """Extract JSON from AI response, handling markdown code fences and extra text."""
    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    code_fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(code_fence_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding JSON object in text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    # Return raw text wrapped in a dict if all parsing fails
    return {"raw_response": text, "parse_error": True}


def call_gemini(user_input, patient_context=None):
    """
    Call Google Gemini API using whichever SDK is loaded.
    Falls back to Groq if both fail or if neither SDK is installed.
    """
    if not HAS_NEW_GENAI and not HAS_LEGACY_GENAI:
        raise RuntimeError("No Google GenAI SDK is installed in the current Python environment.")

    # Build prompt with patient context if available
    prompt_parts = []
    if patient_context:
        context_str = "\n".join(
            f"- {k}: {v}" for k, v in patient_context.items() if v
        )
        prompt_parts.append(f"Patient Profile:\n{context_str}\n")

    prompt_parts.append(f"Patient's Complaint:\n{user_input}")
    full_prompt = "\n".join(prompt_parts)

    try:
        if HAS_NEW_GENAI:
            # Use new SDK
            client = genai.Client(api_key=Config.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=Config.GEMINI_MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=GEMINI_SYSTEM_PROMPT,
                    temperature=0.2,
                    max_output_tokens=4096,
                ),
            )
            return _extract_json(response.text)

        elif HAS_LEGACY_GENAI:
            # Use old SDK wrapper
            legacy_genai.configure(api_key=Config.GEMINI_API_KEY)
            # Map new flash model name to legacy model name if needed
            model_name = Config.GEMINI_MODEL
            
            model = legacy_genai.GenerativeModel(
                model_name=model_name,
                system_instruction=GEMINI_SYSTEM_PROMPT
            )
            response = model.generate_content(
                full_prompt,
                generation_config={"temperature": 0.2}
            )
            return _extract_json(response.text)

    except Exception as e:
        logger.warning("[AI Service] Gemini API call failed: %s. Falling back to Groq for analysis.", e)
        raise


def call_groq_as_analyst(user_input, patient_context=None):
    """
    Fallback method: Calls Groq to perform the initial "Medical Analyst" role
    using the Gemini prompt when Gemini's API is rate-limited or unavailable.
    """
    try:
        client = Groq(api_key=Config.GROQ_API_KEY)

        prompt_parts = []
        if patient_context:
            context_str = "\n".join(
                f"- {k}: {v}" for k, v in patient_context.items() if v
            )
            prompt_parts.append(f"Patient Profile:\n{context_str}\n")

        prompt_parts.append(f"Patient's Complaint:\n{user_input}")
        full_prompt = "\n".join(prompt_parts)

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": GEMINI_SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt},
            ],
            model=Config.GROQ_MODEL,
            temperature=0.2,
            max_tokens=4096,
        )

        response_text = chat_completion.choices[0].message.content
        result = _extract_json(response_text)
        return result
    except Exception as e:
        return {
            "error": True,
            "message": f"Groq fallback analyst error: {str(e)}",
            "severity": "Unknown",
        }


def call_groq(user_input, gemini_response):
    """
    Call Groq API for senior doctor validation of Gemini's analysis.
    """
    try:
        client = Groq(api_key=Config.GROQ_API_KEY)

        validation_prompt = f"""CASE FOR REVIEW:

Patient's Original Complaint (this is the ONLY source of truth):
\"{user_input}\"

Junior AI Analyst's Report:
{json.dumps(gemini_response, indent=2)}

INSTRUCTIONS:
1. Compare the analyst's report against the patient's ORIGINAL complaint.
2. Remove any condition or detail that the patient NEVER mentioned.
3. Verify all medicine suggestions are safe OTC options available in India.
4. Remove any unsafe or prescription-only recommendations.
5. Check for missed emergency red flags.
6. Generate your validated final report as JSON."""

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": GROQ_SYSTEM_PROMPT},
                {"role": "user", "content": validation_prompt},
            ],
            model=Config.GROQ_MODEL,
            temperature=0.2,
            max_tokens=4096,
        )

        response_text = chat_completion.choices[0].message.content
        return _extract_json(response_text)

    except Exception as e:
        return {
            "error": True,
            "message": f"Groq API error: {str(e)}",
        }


def ai_doctor_pipeline(user_input, patient_context=None):
    """
    Main AI Doctor Pipeline.
    User Input -> Gemini (Medical Analyst) -> Groq (Senior Doctor Validator) -> Final Report.
    If Gemini fails, falls back to Groq (Medical Analyst) -> Groq (Senior Doctor Validator).
    """
    is_fallback = False
    try:
        # Step 1: Attempt Gemini symptom analysis
        gemini_response = call_gemini(user_input, patient_context)
    except Exception:
        # Step 1 Fallback: Call Groq to run the Analyst prompt
        is_fallback = True
        logger.info("[Resilience] Initiating Groq Analyst Fallback due to Gemini API failure.")
        gemini_response = call_groq_as_analyst(user_input, patient_context)

    # Check for Analyst errors
    if gemini_response.get("error"):
        return {
            "success": False,
            "stage": "analysis",
            "gemini_response": gemini_response,
            "groq_response": None,
            "is_fallback": is_fallback
        }

    # Step 2: Groq validates the analysis output
    groq_response = call_groq(user_input, gemini_response)

    # Determine severity and emergency status
    severity = gemini_response.get("severity", "Unknown")
    is_emergency = severity == "Emergency"

    return {
        "success": True,
        "gemini_response": gemini_response,
        "groq_response": groq_response,
        "severity": severity,
        "is_emergency": is_emergency,
        "is_fallback": is_fallback
    }
