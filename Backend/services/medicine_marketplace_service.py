"""
services/marketplace_service.py
--------------------------------
Dataset-backed medicine marketplace helpers.

Loads OTC medicines from the CSV dataset, derives display fields for the
frontend cards, and optionally uses Groq to narrow the list down to medicines
that are relevant to a symptom description.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from groq import Groq

from config import Config


DATASET_PATH = Path(__file__).resolve().parents[1] / "dataset" / "India Medicines and Drug Info Dataset.csv"

MEDICINE_FORM_KEYWORDS = [
    "tablet",
    "capsule",
    "syrup",
    "suspension",
    "drops",
    "ointment",
    "cream",
    "gel",
    "spray",
    "solution",
    "lozenge",
    "injection",
    "powder",
    "sachet",
    "granules",
    "nasal",
    "drop",
]

MAX_DB_LENGTHS = {
    "name": 200,
    "generic_name": 200,
    "category": 100,
    "common_dosage": 200,
    "warnings": 500,
    "price_range": 50,
}

CATEGORY_RULES = [
    (("fever", "headache", "pain", "ache", "body pain", "migraine", "inflammation"), ("Pain & Fever", "Helps reduce pain, fever, and inflammation.")),
    (("cough", "cold", "sore throat", "throat", "congestion", "runny nose", "sneezing"), ("Cold & Cough", "Helps ease cold, cough, throat irritation, or congestion.")),
    (("acidity", "heartburn", "gas", "indigestion", "stomach", "reflux", "vomiting", "diarrhea", "constipation"), ("Digestive", "Supports digestion and relief from common stomach discomforts.")),
    (("allergy", "itch", "hives", "sneezing", "rhinitis", "hay fever"), ("Allergy", "Helps relieve allergy symptoms such as itching or sneezing.")),
    (("burn", "cut", "wound", "first aid", "abrasion"), ("First Aid", "Used for minor first-aid care and wound support.")),
    (("muscle", "joint", "sprain", "back pain", "body ache"), ("Pain Relief", "Helps with muscle, joint, or back discomfort.")),
    (("skin", "fungal", "rash", "acne", "itching"), ("Skin Care", "Supports common skin-related concerns.")),
]

SYMPTOM_CATEGORY_HINTS = [
    (("fever", "headache", "body pain", "pain", "ache", "migraine"), "Pain & Fever", ("pain", "fever", "paracetamol", "ibuprofen", "combiflam")),
    (("cough", "cold", "sore throat", "congestion", "sneezing"), "Cold & Cough", ("cough", "cold", "throat", "congestion", "decongest")),
    (("acidity", "gas", "heartburn", "indigestion", "stomach", "bloating", "vomit", "diarrhea", "constipation"), "Digestive", ("acidity", "gas", "digestive", "ORS", "lactulose", "antacid")),
    (("allergy", "itch", "hives", "sneezing", "runny nose", "rhinitis"), "Allergy", ("allergy", "antihistamine", "cetirizine", "fexofenadine")),
    (("burn", "cut", "wound"), "First Aid", ("burn", "wound", "antiseptic", "povidone", "betadine")),
    (("muscle", "joint", "sprain", "back pain"), "Pain Relief", ("muscle", "joint", "diclofenac", "menthol")),
]


def _normalize(value):
    return re.sub(r"\s+", " ", (value or "").strip())


def _truncate(value, max_length):
    if value is None:
        return None
    text = _normalize(value)
    if max_length and len(text) > max_length:
        return text[: max_length - 1].rstrip() + "…"
    return text


def _safe_lower(value):
    return _normalize(value).lower()


def _infer_form(*values):
    combined = " ".join(_safe_lower(value) for value in values if value)
    for keyword in MEDICINE_FORM_KEYWORDS:
        if keyword in combined:
            if keyword == "drop":
                return "Drops"
            return keyword.title()
    return "Medicine"


def _extract_strength(text):
    combined = _normalize(text)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|iu|units?)", combined, re.IGNORECASE)
    if match:
        return f"{match.group(1)} {match.group(2).upper()}"
    return ""


def _extract_generic_name(product_name, composition, medicine_type):
    candidates = [
        _normalize(composition),
        _normalize(medicine_type),
        _normalize(product_name),
    ]
    for candidate in candidates:
        if candidate:
            candidate = re.sub(r"\bMRP\b.*$", "", candidate, flags=re.IGNORECASE).strip()
            candidate = re.sub(r"\bADD\b$", "", candidate, flags=re.IGNORECASE).strip()
            if len(candidate) > 20:
                return candidate
    return _normalize(product_name) or _normalize(composition) or _normalize(medicine_type) or ""


def _extract_pack_size(text):
    combined = _normalize(text)
    match = re.search(r"(strip of \d+\s+\w+)", combined, re.IGNORECASE)
    if match:
        return match.group(1).capitalize()
    return ""


def _infer_category(display_name, product_name, composition, medicine_type):
    combined = " ".join(
        part for part in [_safe_lower(display_name), _safe_lower(product_name), _safe_lower(composition), _safe_lower(medicine_type)] if part
    )
    for keywords, category in CATEGORY_RULES:
        if any(keyword in combined for keyword in keywords):
            return category[0], category[1]
    return "General", "General marketplace medicine listing extracted from the dataset."


def _infer_what_it_does(product_name, category, category_description, composition):
    product_text = _normalize(product_name)
    if product_text:
        lower_text = product_text.lower()
        for marker in (" for ", " relief", " supports ", " helps ", " used for "):
            if marker.strip() in lower_text:
                return product_text
        if "|" in product_text:
            parts = [part.strip() for part in product_text.split("|") if part.strip()]
            if len(parts) > 1:
                return parts[1]
    if composition:
        return f"Supports care with {composition}."
    return category_description


def _build_catalog_record(row, row_number):
    medicine_name = _normalize(row.get("Medicine Name"))
    product_name = _normalize(row.get("Product Name"))
    image_url = _normalize(row.get("Image URL"))
    price = _normalize(row.get("Price"))
    prescription_required = _safe_lower(row.get("Is Prescription Required?")) in {"true", "1", "yes", "y"}
    medicine_type = _normalize(row.get("Type of Medicine"))
    composition = _normalize(row.get("Composition"))

    display_name = medicine_name or product_name or f"Medicine {row_number}"
    category, category_description = _infer_category(display_name, product_name, composition, medicine_type)
    medicine_form = _infer_form(medicine_name, product_name, medicine_type)
    strength = _extract_strength(" ".join([medicine_name, product_name, composition]))
    pack_size = _extract_pack_size(medicine_type) or _extract_pack_size(product_name)
    what_it_does = _infer_what_it_does(product_name, category, category_description, composition)
    generic_name = _extract_generic_name(product_name, composition, medicine_type)

    dosage_parts = []
    if strength:
        dosage_parts.append(f"Strength: {strength}")
    if pack_size:
        dosage_parts.append(pack_size)
    if not dosage_parts:
        dosage_parts.append("Use only as directed on the pack or by a pharmacist.")

    searchable_text = " ".join(
        [display_name, product_name, composition, medicine_type, category, what_it_does, price]
    ).lower()

    record_id = int(hashlib.sha1(f"{row_number}:{display_name}:{price}".encode("utf-8")).hexdigest()[:12], 16)

    return {
        "id": record_id,
        "name": _truncate(display_name, MAX_DB_LENGTHS["name"]),
        "generic_name": _truncate(generic_name, MAX_DB_LENGTHS["generic_name"]),
        "category": _truncate(category, MAX_DB_LENGTHS["category"]),
        "purpose": what_it_does,
        "common_dosage": _truncate(" | ".join(dosage_parts), MAX_DB_LENGTHS["common_dosage"]),
        "warnings": _truncate(
            "Prescription medicine. Please consult a clinician before use."
            if prescription_required
            else "Follow the label instructions and ask a pharmacist if unsure.",
            MAX_DB_LENGTHS["warnings"],
        ),
        "price_range": _truncate(price, MAX_DB_LENGTHS["price_range"]),
        "product_name": product_name,
        "image_url": image_url,
        "medicine_type": medicine_form,
        "composition": composition,
        "prescription_required": prescription_required,
        "what_it_does": what_it_does,
        "dosage": " | ".join(dosage_parts),
        "type": medicine_form,
        "searchable_text": searchable_text,
    }


@lru_cache(maxsize=1)
def load_marketplace_catalog():
    """Load OTC marketplace medicines from the dataset once and cache them."""
    if not DATASET_PATH.exists():
        return []

    catalog = []
    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as dataset_file:
        reader = csv.DictReader(dataset_file)
        for row_number, row in enumerate(reader, start=1):
            prescription_required = _safe_lower(row.get("Is Prescription Required?"))
            if prescription_required not in {"false", "0", "no"}:
                continue

            medicine_name = _normalize(row.get("Medicine Name"))
            product_name = _normalize(row.get("Product Name"))
            if not medicine_name and not product_name:
                continue

            catalog.append(_build_catalog_record(row, row_number))

    return catalog


def _score_candidate(medicine, symptoms_text):
    searchable_text = medicine.get("searchable_text", "")
    score = 0
    for token in re.findall(r"[a-z0-9]+", symptoms_text.lower()):
        if token and token in searchable_text:
            score += 3

    medicine_name = medicine.get("name", "").lower()
    product_name = medicine.get("product_name", "").lower()
    composition = medicine.get("composition", "").lower()
    category = medicine.get("category", "").lower()

    for keyword_group, category_name, hint_words in SYMPTOM_CATEGORY_HINTS:
        if any(keyword in symptoms_text.lower() for keyword in keyword_group):
            if category == category_name.lower():
                score += 8
            if any(hint in medicine_name or hint in product_name or hint in composition for hint in hint_words):
                score += 5

    if medicine.get("prescription_required"):
        score -= 20

    return score


def shortlist_medicines_for_symptoms(symptoms, limit=30):
    """Return a compact shortlist of candidate medicines for Groq review."""
    catalog = load_marketplace_catalog()
    if not catalog:
        return []

    scored_catalog = [
        (medicine, _score_candidate(medicine, symptoms))
        for medicine in catalog
    ]
    ranked = sorted(scored_catalog, key=lambda item: item[1], reverse=True)
    shortlist = [medicine for medicine, score in ranked if score > 0]

    if not shortlist:
        shortlist = [medicine for medicine, _ in ranked[:limit]]

    return shortlist[:limit]


def _groq_client():
    if not getattr(Config, "GROQ_API_KEY", None):
        return None
    return Groq(api_key=Config.GROQ_API_KEY)


def recommend_medicines_with_groq(symptoms, current_user=None, limit=8):
    """Use Groq to pick only the medicines that plausibly help the symptoms."""
    shortlist = shortlist_medicines_for_symptoms(symptoms, limit=30)
    if not shortlist:
        return []

    client = _groq_client()
    if client is None:
        return shortlist[:limit]

    compact_catalog = [
        {
            "id": medicine["id"],
            "name": medicine["name"],
            "category": medicine["category"],
            "purpose": medicine["purpose"],
            "dosage": medicine["dosage"],
            "type": medicine["type"],
            "price": medicine["price_range"],
            "composition": medicine["composition"],
            "prescription_required": medicine["prescription_required"],
        }
        for medicine in shortlist
    ]

    allergy_context = ""
    if current_user and current_user.known_allergies:
        allergy_context = f"Known allergies: {current_user.known_allergies}"

    prompt = f"""
Symptoms:
{symptoms}

{allergy_context}

Candidate medicines from the marketplace:
{json.dumps(compact_catalog, indent=2)}

Task:
- Return ONLY medicines that could reasonably help the symptoms.
- Do NOT include prescription-only medicines.
- Prefer the safest OTC matches.
- If an item is not relevant, omit it.
- Return strict JSON with this shape:
{{
  "medicines": [
    {{
      "id": 123,
      "reason": "short professional reason",
      "match_strength": "high | medium | low"
    }}
  ]
}}
"""

    try:
        response = client.chat.completions.create(
            model=Config.GROQ_MODEL,
            temperature=0.2,
            max_tokens=1200,
            messages=[
                {
                    "role": "system",
                    "content": "You are a careful clinical triage assistant who only selects safe OTC medicine matches from a provided catalog. Never invent medicines outside the list.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        response_text = response.choices[0].message.content or ""
        parsed = _extract_json_blob(response_text)
        allowed_ids = {
            item.get("id")
            for item in parsed.get("medicines", [])
            if isinstance(item, dict) and item.get("id") is not None
        }

        if not allowed_ids:
            return shortlist[:limit]

        lookup = {medicine["id"]: medicine for medicine in shortlist}
        results = []
        for item in parsed.get("medicines", []):
            medicine_id = item.get("id")
            source = lookup.get(medicine_id)
            if not source:
                continue
            enriched = dict(source)
            enriched["groq_reason"] = item.get("reason", "")
            enriched["match_strength"] = item.get("match_strength", "medium")
            results.append(enriched)
            if len(results) >= limit:
                break

        return results or shortlist[:limit]

    except Exception:
        return shortlist[:limit]


def _extract_json_blob(text):
    """Parse strict JSON or recover JSON from code fences / surrounding text."""
    try:
        return json.loads(text)
    except Exception:
        pass

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except Exception:
            pass

    start_index = text.find("{")
    end_index = text.rfind("}")
    if start_index != -1 and end_index != -1 and end_index > start_index:
        try:
            return json.loads(text[start_index : end_index + 1])
        except Exception:
            pass

    return {"medicines": []}
