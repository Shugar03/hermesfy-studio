"""Moodboard module for Hermesfy — estética curada para generación.

Módulo que permite construir moodboards visuales a partir de
referencias (Pinterest, boards, uploads) y convertirlos en un
MOOD_SPEC estructurado que guía la generación de imágenes con
coherencia estética + manual de marca.
"""
from hermesfy.moodboard.orchestrator import MoodboardOrchestrator
from hermesfy.moodboard.database import MoodboardDB
from hermesfy.moodboard.synthesizer import MoodSpec
