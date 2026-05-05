"""Search Templates — queries predefinidas para moodboards por formato."""
from __future__ import annotations

# Templates base por categoría de formato
# {concept} se reemplaza con el concepto del usuario
SEARCH_TEMPLATES: dict[str, list[str]] = {
    "default": [
        "{concept} advertising campaign",
        "{concept} editorial photography",
        "{concept} social media post design",
        "{concept} moodboard visual reference inspiration",
    ],
    "advertising": [
        "{concept} advertising campaign",
        "{concept} commercial photography",
        "{concept} ad poster billboard design",
        "{concept} advertising creative concept",
    ],
    "editorial": [
        "{concept} editorial photography",
        "{concept} magazine lookbook editorial",
        "{concept} fashion editorial photoshoot",
        "{concept} lifestyle editorial",
    ],
    "social_media": [
        "{concept} instagram post design",
        "{concept} social media feed aesthetic",
        "{concept} social media campaign creative",
        "{concept} instagram story advertisement",
    ],
    "product": [
        "{concept} product photography studio",
        "{concept} product advertising commercial",
        "{concept} packshot product design",
        "{concept} product launch campaign",
    ],
    "hospitality": [
        "{concept} hotel advertising campaign",
        "{concept} hospitality photography editorial",
        "{concept} hotel social media post",
        "{concept} luxury resort magazine ad",
    ],
    "fashion": [
        "{concept} fashion campaign advertising",
        "{concept} fashion editorial photoshoot",
        "{concept} luxury brand campaign",
        "{concept} fashion lookbook editorial",
    ],
}

# Palabras clave para scoring de alt text
FORMAT_KEYWORDS = {
    "advertising", "ad", "campaign", "commercial", "poster",
    "social media", "instagram", "feed", "post", "story",
    "editorial", "magazine", "lookbook", "photography",
    "product", "packshot", "studio", "branding",
}

NEGATIVE_KEYWORDS = {
    "food", "recipe", "diy", "tutorial", "cat", "dog",
    "pet", "wedding", "nails", "makeup", "drawing",
    "illustration", "cartoon", "meme",
}

STYLE_KEYWORDS = {
    "luxury", "premium", "minimalist", "elegant", "modern",
    "vintage", "retro", "gothic", "dark", "romantic",
    "boho", "rustic", "industrial", "scandinavian",
    "tropical", "coastal", "mountain",
}


def generate_queries(
    concept: str,
    format: str = "default",
    extra_templates: list[str] | None = None,
) -> list[str]:
    """Genera queries de búsqueda a partir del concepto y formato."""
    templates = SEARCH_TEMPLATES.get(format, SEARCH_TEMPLATES["default"])
    if extra_templates:
        templates = templates + extra_templates
    return [t.format(concept=concept) for t in templates]


def score_image(alt_text: str, concept_keywords: list[str] | None = None) -> int:
    """Puntúa relevancia de una imagen por su alt text.

    Returns:
        int: Score positivo = relevante. -10 = descartar (negativo match).
    """
    text = (alt_text or "").lower().strip()
    if not text or text in ("", "-", "image", "photo", "pin", "img"):
        return -10

    score = 0

    # Palabras de formato (advertising, campaign, etc.)
    for w in FORMAT_KEYWORDS:
        if w in text:
            score += 5

    # Palabras de estilo
    for w in STYLE_KEYWORDS:
        if w in text:
            score += 3

    # Palabras del concepto
    if concept_keywords:
        for w in concept_keywords:
            wl = w.lower()
            if wl in text:
                score += 3

    # Penalizar descripciones genéricas
    if len(text) < 15:
        score -= 5

    # Bloquear contenido no deseado
    for w in NEGATIVE_KEYWORDS:
        if w in text:
            return -10

    return score
