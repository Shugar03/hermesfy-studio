"""
Hermesfy Intent Router — Natural Language → Image Generation Intent

Interprets user requests in natural language and determines:
- Action: generate (new image) vs edit (modify existing)
- Subject: what the image is about
- Style/aesthetic preferences
- Which model to use
- How to construct the optimal prompt

Usage:
    from engine.intent_router import IntentRouter

    router = IntentRouter()
    intent = router.parse("haceme un ad de Nike con fondo negro")
    # Returns: Intent(action="generate", subject="Nike", style="dark", ...)

    intent = router.parse("cambiá el fondo a playa", reference_image="path/to/img.png")
    # Returns: Intent(action="edit", change="background", target="beach", ...)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("hermesfy.intent_router")


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class Intent:
    """Parsed intent from user's natural language request."""
    action: str = "generate"  # "generate" | "edit" | "refine" | "validate"
    subject: str = ""  # What the image is about
    content_type: str = "product"  # product, lifestyle, social_media, food, etc.
    style: str = "clean"  # dark, luxury, clean, neon, fitness, tech, gradient
    size: str = "1080x1080"  # Output size
    model_preference: Optional[str] = None  # Specific model requested
    prompt: str = ""  # Generated prompt for the model
    negative_prompt: str = ""  # What to avoid
    reference_image: Optional[str] = None  # Path/URL to reference image
    edit_instructions: str = ""  # For edit action: what to change
    preserve_instructions: str = ""  # For edit action: what to keep
    language: str = "es"  # es or en
    confidence: float = 0.0  # How confident we are in the parse
    raw_input: str = ""  # Original user input

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "subject": self.subject,
            "content_type": self.content_type,
            "style": self.style,
            "size": self.size,
            "model_preference": self.model_preference,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "reference_image": self.reference_image,
            "edit_instructions": self.edit_instructions,
            "preserve_instructions": self.preserve_instructions,
            "language": self.language,
            "confidence": self.confidence,
        }


# ── Keyword Maps ─────────────────────────────────────────────────────────────

# Content type detection keywords
CONTENT_TYPE_KEYWORDS = {
    "product": ["zapatilla", "zapatillas", "shoe", "sneaker", "product", "producto",
                 "camisa", "reloj", "auricular", "fone", "phone", "laptop", "camera",
                 "perfume", "cosmético", "cosmetico", "skincare", "cream", "crema"],
    "food": ["comida", "food", "restaurant", "restaurante", "pizza", "hamburguesa",
             "burger", "sushi", "café", "cafe", "coffee", "pastel", "cake", "bebida",
             "drink", "cocktail", "cerveza", "beer", "wine", "vino"],
    "fashion": ["moda", "fashion", "vestido", "dress", "outfit", "look", "style",
                "ropa", "clothing", "accesorio", "accessory", "billetera", "wallet"],
    "travel": ["hotel", "playa", "beach", "montaña", "mountain", "viaje", "travel",
               "turismo", "tourism", "destino", "destination", "vacaciones", "vacation"],
    "tech": ["tecnología", "tech", "gadget", "smartphone", "tablet", "robot",
             "futurista", "futuristic", "cyber", "neon", "digital"],
    "beauty": ["belleza", "beauty", "maquillaje", "makeup", "skincare", "cabello",
               "hair", "uñas", "nails", "spa", "salon"],
    "fitness": ["fitness", "gym", "ejercicio", "workout", "deporte", "sport",
                "running", "yoga", "musculación"],
    "real_state": ["casa", "house", "departamento", "apartment", "oficina", "office",
                   "edificio", "building", "inmobiliario", "real estate", "inmueble"],
    "social_media": ["post", "story", "stories", "reel", "carrusel", "carousel",
                     "instagram", "tiktok", "facebook", "banner", "thumbnail"],
    "editorial": ["revista", "magazine", "portada", "cover", "editorial", "fashion",
                  "editorial photography"],
}

# Style detection keywords
STYLE_KEYWORDS = {
    "dark": ["oscuro", "dark", "noche", "night", "sombras", "shadow", "moody",
             "noir", "black", "negro"],
    "luxury": ["lujo", "luxury", "elegante", "elegant", "premium", "exclusive",
               "exclusivo", "gold", "dorado", "champagne"],
    "clean": ["limpio", "clean", "minimal", "minimalista", "simple", "blanco",
              "white", "studio", "claro", "light"],
    "neon": ["neon", "neón", "cyberpunk", "futurista", "futuristic", "glow",
             "brillante", "bright", "electric"],
    "fitness": ["energía", "energy", "power", "fuerza", "intense", "intenso",
                "dynamic", "dinámico"],
    "tech": ["tech", "tecnología", "futurista", "futuristic", "digital", "cyber",
             "holographic", "holográfico"],
    "gradient": ["gradiente", "gradient", "colorful", "colores", "vibrant",
                 "vibrante", "sunset", "atardecer"],
    "natural": ["natural", "orgánico", "organic", "verde", "green", "earth",
                "tierra", "botanical", "botánico"],
}

# Edit action keywords
EDIT_KEYWORDS = {
    "background": ["fondo", "background", "backdrop", "escenario"],
    "color": ["color", "colour", "paleta", "palette"],
    "text": ["texto", "text", "letras", "letters", "título", "title",
             "headline", "cabeza"],
    "logo": ["logo", "logotipo", "marca", "brand"],
    "product": ["producto", "product", "zapatilla", "shoe", "objeto", "object"],
    "layout": ["layout", "diseño", "design", "composición", "composition"],
    "remove": ["quitar", "remove", "eliminar", "delete", "borrar"],
    "add": ["agregar", "add", "añadir", "poner", "put", "incluir", "include"],
    "change": ["cambiar", "change", "modificar", "modify", "actualizar", "update"],
    "make": ["hacer", "make", "crear", "create", "generar", "generate"],
}

# Size presets
SIZE_PRESETS = {
    "square": "1080x1080",
    "portrait": "1080x1350",
    "landscape": "1350x1080",
    "story": "1080x1920",
    "reel": "1080x1920",
    "wide": "1920x1080",
    "banner": "1500x500",
    "post": "1080x1080",
    "cover": "1640x856",
    "a4": "2480x3508",
}

# Spanish → English prompt translation for common terms
ES_TO_EN = {
    "zapatilla": "sneaker",
    "zapatillas": "sneakers",
    "fondo": "background",
    "playa": "beach",
    "montaña": "mountain",
    "ciudad": "city",
    "noche": "night",
    "atardecer": "sunset",
    "amanecer": "sunrise",
    "lujo": "luxury",
    "elegante": "elegant",
    "minimalista": "minimalist",
    "profesional": "professional",
    "publicidad": "advertising",
    "anuncio": "advertisement",
    "oferta": "offer",
    "descuento": "discount",
    "nuevo": "new",
    "nueva": "new",
    "premium": "premium",
    "exclusivo": "exclusive",
    "moderno": "modern",
    "clásico": "classic",
    "color": "color",
    "colores": "colors",
    "rojo": "red",
    "azul": "blue",
    "negro": "black",
    "blanco": "white",
    "dorado": "gold",
    "verde": "green",
}


# ── Intent Router ────────────────────────────────────────────────────────────

class IntentRouter:
    """
    Parse natural language user requests into structured intents.

    Uses keyword-based heuristics (no LLM dependency) for fast, reliable
    parsing. Can be extended with LLM calls for complex/ambiguous inputs.
    """

    def __init__(self, llm_provider=None):
        """
        Initialize the intent router.

        Args:
            llm_provider: Optional LLM provider for complex parsing.
                         If None, uses keyword-based heuristics only.
        """
        self.llm_provider = llm_provider
        logger.info("IntentRouter initialized (llm=%s)", "yes" if llm_provider else "no")

    def parse(self, user_input: str, reference_image: Optional[str] = None) -> Intent:
        """
        Parse a user's natural language request into a structured Intent.

        Args:
            user_input: The user's request in natural language.
            reference_image: Optional path/URL to a reference image.

        Returns:
            Intent object with all parsed fields.
        """
        text = user_input.strip().lower()
        lang = self._detect_language(text)

        intent = Intent(
            raw_input=user_input,
            reference_image=reference_image,
            language=lang,
        )

        # Step 1: Detect action (generate vs edit)
        intent.action = self._detect_action(text, reference_image)

        # Step 2: Detect content type
        intent.content_type = self._detect_content_type(text)

        # Step 3: Detect style
        intent.style = self._detect_style(text)

        # Step 4: Detect size
        intent.size = self._detect_size(text)

        # Step 5: Detect subject
        intent.subject = self._extract_subject(text)

        # Step 6: Detect model preference
        intent.model_preference = self._detect_model_preference(text)

        # Step 7: Build prompt based on action
        if intent.action == "edit":
            intent.edit_instructions = self._extract_edit_instructions(text)
            intent.preserve_instructions = self._extract_preserve_instructions(text)
            intent.prompt = self._build_edit_prompt(intent)
        else:
            intent.prompt = self._build_generate_prompt(intent)

        # Step 8: Build negative prompt
        intent.negative_prompt = self._build_negative_prompt(intent)

        # Step 9: Calculate confidence
        intent.confidence = self._calculate_confidence(intent)

        logger.info(
            "Parsed intent: action=%s, content=%s, style=%s, confidence=%.2f",
            intent.action, intent.content_type, intent.style, intent.confidence,
        )

        return intent

    # ── Detection Methods ────────────────────────────────────────────────

    def _detect_language(self, text: str) -> str:
        """Detect if the input is Spanish or English."""
        es_indicators = ["haceme", "hazme", "poné", "pone", "cambialo", "cambia",
                        "quiero", "necesito", "como", "así", "asi", "fondo",
                        "zapatilla", "producto", "anuncio", "publicidad"]
        en_indicators = ["make", "create", "generate", "change", "put", "i want",
                        "i need", "like", "background", "shoe", "product", "ad"]

        es_count = sum(1 for w in es_indicators if w in text)
        en_count = sum(1 for w in en_indicators if w in text)

        return "es" if es_count >= en_count else "en"

    def _detect_action(self, text: str, reference_image: Optional[str] = None) -> str:
        """Detect if the user wants to generate, edit, refine, or validate."""
        edit_indicators = ["cambiar", "cambiá", "cambia", "modificar", "edit",
                          "editar", "quitar", "remove", "agregar", "add",
                          "poner", "put", "actualizar", "update", "ajustar",
                          "ajusta", "adjust", "mejorar", "improve"]
        refine_indicators = ["mejorar", "improve", "refinar", "refine",
                            "ajustar", "adjust", "más", "more", "menos", "less"]
        validate_indicators = ["verificar", "verify", "validar", "validate",
                              "chequear", "check", "revisar", "review"]

        # If reference image exists and edit keywords present → edit
        if reference_image:
            for kw in edit_indicators:
                if kw in text:
                    return "edit"

        # Check for edit keywords
        for kw in edit_indicators:
            if kw in text:
                return "edit"

        # Check for refine keywords
        for kw in refine_indicators:
            if kw in text:
                return "refine"

        # Check for validate keywords
        for kw in validate_indicators:
            if kw in text:
                return "validate"

        return "generate"

    def _detect_content_type(self, text: str) -> str:
        """Detect the type of content (product, food, fashion, etc.)."""
        scores = {}
        for content_type, keywords in CONTENT_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[content_type] = score

        if scores:
            return max(scores, key=scores.get)
        return "product"  # Default

    def _detect_style(self, text: str) -> str:
        """Detect the visual style."""
        scores = {}
        for style, keywords in STYLE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[style] = score

        if scores:
            return max(scores, key=scores.get)
        return "clean"  # Default

    def _detect_size(self, text: str) -> str:
        """Detect the desired output size."""
        # Check for dimension patterns like "1080x1080" FIRST (highest priority)
        dim_match = re.search(r'(\d{3,4})\s*x\s*(\d{3,4})', text)
        if dim_match:
            return f"{dim_match.group(1)}x{dim_match.group(2)}"

        # Check for preset size mentions
        for preset, dimensions in SIZE_PRESETS.items():
            if preset in text:
                return dimensions

        # Default based on content type hints
        if any(w in text for w in ["story", "stories", "reel", "vertical"]):
            return "1080x1920"
        if any(w in text for w in ["banner", "wide", "horizontal", "landscape"]):
            return "1920x1080"

        return "1080x1080"  # Default square

    def _extract_subject(self, text: str) -> str:
        """Extract the main subject from the text."""
        # Common patterns: "haceme un ad de X", "create an ad for X", "imagen de X"
        patterns = [
            r'(?:ad|anuncio|imagen|image|foto|photo|poster|flyer)\s+(?:de|of|para|for)\s+(.+?)(?:\s+con\s|\s+en\s|\s+with\s|\s+$)',
            r'(?:haceme|hazme|make|create|genera|generate|dame|give)\s+(?:un|una|a|an)?\s*(.+?)(?:\s+con\s|\s+en\s|\s+with\s|\s+$)',
            r'(?:producto|product|zapatilla|sneaker|shoe)\s+(.+?)(?:\s+con\s|\s+en\s|\s+with\s|\s+$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                subject = match.group(1).strip()
                # Clean up common fillers
                fillers = ["por favor", "please", "gracias", "thanks", "que sea",
                          "que tenga", "with", "con", "en", "on"]
                for filler in fillers:
                    subject = re.sub(rf'\b{filler}\b', '', subject, flags=re.IGNORECASE)
                subject = subject.strip()
                if subject:
                    return subject

        # Fallback: extract nouns
        words = text.split()
        # Remove common verbs and prepositions
        stop_words = {"haceme", "hazme", "make", "create", "generate", "poné",
                     "pone", "put", "un", "una", "a", "an", "el", "la", "the",
                     "de", "of", "del", "con", "with", "en", "on", "para", "for",
                     "por", "favor", "please", "como", "like", "así", "asi"}
        nouns = [w for w in words if w not in stop_words and len(w) > 2]
        return " ".join(nouns[:3]) if nouns else "product"

    def _detect_model_preference(self, text: str) -> Optional[str]:
        """Detect if the user prefers a specific model."""
        model_map = {
            "flux": "flux-schnell",
            "schnell": "flux-schnell",
            "pro": "flux-2-pro",
            "recraft": "recraft-v3",
            "nano": "nano-banana-pro",
            "banana": "nano-banana-pro",
            "ideogram": "ideogram-v3",
            "gpt": "gpt-image-2",
            "imagen": "gpt-image-2",
            "grok": "grok-imagine",
        }
        for keyword, model in model_map.items():
            if keyword in text:
                return model
        return None

    def _extract_edit_instructions(self, text: str) -> str:
        """Extract what the user wants to change."""
        # Pattern: "cambiá X a Y" / "change X to Y"
        patterns = [
            r'(?:cambiar|cambiá|cambia|change|modificar|edit)\s+(.+?)(?:\s+(?:a|to|por|by)\s+(.+?))?(?:\s*$)',
            r'(?:quitar|remove|eliminar|delete)\s+(.+?)(?:\s*$)',
            r'(?:agregar|add|añadir|poner|put)\s+(.+?)(?:\s*$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()

        return text

    def _extract_preserve_instructions(self, text: str) -> str:
        """Extract what the user wants to keep. Returns specific elements, never 'everything else'."""
        patterns = [
            r'(?:manteniendo|keeping|keep|preservando|preserve|mantener|sin tocar)\s+(.+?)(?:\s*$)',
            r'(?:igual|same|igualito)\s+(.+?)(?:\s*$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # NEVER return "everything else" — it's useless for I2I models
        # Instead, return a specific default based on common edit types
        return ""

    # ── Prompt Building ──────────────────────────────────────────────────

    def _build_generate_prompt(self, intent: Intent) -> str:
        """Build an optimal prompt for image generation."""
        parts = []

        # Style prefix
        style_map = {
            "dark": "dark, moody, dramatic lighting",
            "luxury": "luxury, elegant, premium, gold accents",
            "clean": "clean, minimalist, professional",
            "neon": "neon, cyberpunk, futuristic, glowing",
            "fitness": "energetic, dynamic, powerful",
            "tech": "tech, futuristic, digital, holographic",
            "gradient": "colorful, vibrant, gradient background",
            "natural": "natural, organic, earthy tones",
        }
        if intent.style in style_map:
            parts.append(style_map[intent.style])

        # Content type specifics
        content_map = {
            "product": "professional product photography, studio lighting",
            "food": "food photography, appetizing, warm lighting",
            "fashion": "fashion photography, editorial, stylized",
            "travel": "travel photography, scenic, breathtaking",
            "tech": "tech product, sleek, modern",
            "beauty": "beauty photography, soft lighting, flawless",
            "fitness": "fitness photography, athletic, powerful",
            "real_state": "real estate photography, architectural, inviting",
            "social_media": "social media content, eye-catching, engaging",
            "editorial": "editorial photography, magazine quality",
        }
        if intent.content_type in content_map:
            parts.append(content_map[intent.content_type])

        # Subject
        if intent.subject:
            # Translate to English if needed
            subject_en = self._translate_to_english(intent.subject)
            parts.append(subject_en)

        # Quality boosters
        parts.append("high resolution, sharp focus, professional, 8K")

        return ", ".join(parts)

    def _build_edit_prompt(self, intent: Intent) -> str:
        """Build a SURGICAL edit prompt. I2I models need explicit keep/change lists."""
        parts = []

        # Explicit preservation (not vague "keep everything")
        if intent.preserve_instructions:
            parts.append(f"KEEP EXACTLY AS-IS: {intent.preserve_instructions}.")
        else:
            parts.append(
                "KEEP EXACTLY AS-IS: the main subject's shape, position, "
                "colors, and all details. Keep the overall composition and layout."
            )

        # Explicit change instruction
        if intent.edit_instructions:
            edit_en = self._translate_to_english(intent.edit_instructions)
            parts.append(f"MODIFY ONLY: {edit_en}.")

        # Hard constraints
        parts.append(
            "DO NOT change anything not listed above. "
            "Maintain identical resolution, quality, and lighting."
        )

        return " ".join(parts)

    def _build_negative_prompt(self, intent: Intent) -> str:
        """Build a negative prompt based on content type."""
        base_negative = "blurry, low quality, distorted, deformed, ugly, bad anatomy"

        content_negatives = {
            "product": "text, watermark, logo, multiple products, cluttered",
            "food": "raw, unappetizing, cold, plastic looking",
            "fashion": "wrinkled, poor fit, mannequin, low quality fabric",
            "travel": "tourists, crowds, overexposed, flat lighting",
            "beauty": "heavy makeup, unnatural, airbrushed, plastic",
            "fitness": "weak, inactive, lazy, static pose",
        }

        negatives = [base_negative]
        if intent.content_type in content_negatives:
            negatives.append(content_negatives[intent.content_type])

        return ", ".join(negatives)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _translate_to_english(self, text: str) -> str:
        """Translate common Spanish terms to English for prompts."""
        words = text.split()
        translated = []
        for word in words:
            lower = word.lower()
            if lower in ES_TO_EN:
                translated.append(ES_TO_EN[lower])
            else:
                translated.append(word)
        return " ".join(translated)

    def _calculate_confidence(self, intent: Intent) -> float:
        """Calculate confidence score for the parsed intent."""
        score = 0.5  # Base score

        # Higher confidence if we found a clear subject
        if intent.subject and len(intent.subject) > 2:
            score += 0.15

        # Higher confidence if style was detected (not default)
        if intent.style != "clean":
            score += 0.1

        # Higher confidence if content type was clearly detected
        if intent.content_type != "product":
            score += 0.1

        # Higher confidence for edit actions with reference image
        if intent.action == "edit" and intent.reference_image:
            score += 0.1

        # Lower confidence for very short inputs
        if len(intent.raw_input.split()) < 3:
            score -= 0.1

        return min(max(score, 0.0), 1.0)
