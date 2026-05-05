"""Orchestrator — pipeline completo del moodboard.

Coordina: searcher → curator → VRH analyze → synthesizer → brand_merge
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from hermesfy.moodboard.database import MoodboardDB
from hermesfy.moodboard.searcher import search_moodboard_sources, PinterestSearcher
from hermesfy.moodboard.curator import curate_images
from hermesfy.moodboard.synthesizer import MoodSpec, Synthesizer
from hermesfy.moodboard.brand_merge import merge_with_brand

logger = logging.getLogger("hermesfy.moodboard.orchestrator")


class MoodboardOrchestrator:
    """Orquesta el pipeline completo de moodboard."""

    def __init__(self):
        self.db = MoodboardDB()

    def run_pipeline(
        self,
        concept: str,
        format: str = "default",
        source: str = "pinterest_search",
        source_url: str | None = None,
        brand: str | None = None,
        tags: str | None = None,
        max_images: int = 15,
        analyze_images: bool = True,
    ) -> dict:
        """Pipeline completo: search → curate → analyze → synthesize → merge.

        Args:
            concept: Concepto del usuario ("hotel lujo selva")
            format: Categoría de formato
            source: Fuente de imágenes
            source_url: URL de board si aplica
            brand: Nombre de marca para DESIGN.md
            tags: Tags CSV para búsqueda
            max_images: Máximo de imágenes finales
            analyze_images: Si True, ejecuta VRH en cada imagen

        Returns:
            Dict con moodboard_id, mood_spec, preview, imágenes, stats
        """
        # 1. Crear moodboard en DB
        mb_id = self.db.create_moodboard(
            concept=concept,
            source=source,
            source_url=source_url,
            format=format,
            brand=brand,
            tags=tags or concept.lower().replace(" ", ", "),
        )

        # 2. Buscar imágenes
        logger.info("Phase 1/5: Searching images (source=%s)", source)
        self.db.update_moodboard(mb_id, status="searching")
        candidates = search_moodboard_sources(
            concept=concept,
            format=format,
            source=source,
            source_url=source_url,
            max_images=max_images * 3,  # Buscar más de los que necesitamos
        )

        if not candidates:
            self.db.update_moodboard(mb_id, status="error", error_msg="No images found")
            return {"moodboard_id": mb_id, "error": "No se encontraron imágenes", "status": "error"}

        # 3. Curar imágenes
        logger.info("Phase 2/5: Curating images")
        images_path = self.db.get_images_path(mb_id)
        curated = curate_images(
            candidates=candidates,
            output_dir=images_path,
            concept=concept,
            max_images=max_images,
        )

        if not curated:
            self.db.update_moodboard(mb_id, status="error", error_msg="No images passed curation")
            return {"moodboard_id": mb_id, "error": "Ninguna imagen pasó la curaduría", "status": "error"}

        self.db.update_moodboard(
            mb_id,
            status="analyzing",
            image_count=len(curated),
            images_path=str(images_path),
            source_data=json.dumps({
                "queries_used": getattr(candidates, "queries_used", None),
                "total_candidates": len(candidates),
                "curated": len(curated),
                "images": [{"fname": c["fname"], "score": c.get("score", 0),
                            "size_kb": c.get("size_kb", 0)} for c in curated],
            }),
        )

        # 4. Analizar con VRH (si está disponible)
        specs = []
        if analyze_images:
            logger.info("Phase 3/5: Analyzing images with VRH")
            for img in curated:
                spec = self._analyze_single_image(img["path"])
                if spec:
                    specs.append(spec)
            logger.info("  VRH analyzed %d/%d images", len(specs), len(curated))
        else:
            logger.info("Phase 3/5: Skipping VRH analysis (analyze_images=False)")

        # 5. Sintetizar
        logger.info("Phase 4/5: Synthesizing mood spec")
        synthesizer = Synthesizer()
        mood_spec = synthesizer.synthesize(
            specs=specs or [],
            session_id=mb_id,
            concept=concept,
        )
        # Si no hay specs, usar los scores como base
        if not specs:
            mood_spec.images_used = len(curated)
            mood_spec.total_images_analyzed = len(curated)

        # 6. Merge con brand
        if brand:
            logger.info("Phase 5/5: Merging with brand '%s'", brand)
            ms_dict = merge_with_brand(mood_spec.to_dict(), brand)
            mood_spec = MoodSpec.from_dict(ms_dict)

        # 7. Generar preview
        preview_md = mood_spec.to_preview_md()

        # 8. Guardar en DB
        self.db.update_moodboard(
            mb_id,
            status="completed",
            mood_spec=json.dumps(mood_spec.to_dict()),
            mood_spec_md=preview_md,
        )

        return {
            "moodboard_id": mb_id,
            "status": "completed",
            "concept": concept,
            "brand": brand,
            "source": source,
            "image_count": len(curated),
            "images": curated,
            "mood_spec": mood_spec.to_dict(),
            "preview_md": preview_md,
        }

    def _analyze_single_image(self, image_path: str) -> dict | None:
        """Analiza una imagen con VRH. Retorna StructuredSpec o None."""
        try:
            from hermesfy.reference.visual_analyzer import VisualAnalyzer
            analyzer = VisualAnalyzer()
            # Por ahora devolvemos un spec básico
            # El VRH completo requiere llamada a visión LLM
            return {"palette": {"colors": []}, "source_path": image_path}
        except ImportError:
            logger.debug("VisualAnalyzer not available, skipping VRH")
            return None

    def regenerate(self, moodboard_id: str, new_concept: str, brand: str | None = None) -> dict | None:
        """Reusa un moodboard existente con un nuevo concepto.

        Toma el MOOD_SPEC de un moodboard previo y lo reaplica
        cambiando solo el sujeto/concepto.
        """
        mb = self.db.get_moodboard(moodboard_id)
        if not mb:
            return None

        spec_json = mb.get("mood_spec")
        if not spec_json:
            return None

        original_spec = MoodSpec.from_dict(json.loads(spec_json))

        # Marcar uso
        self.db.mark_used(moodboard_id)

        return {
            "moodboard_id": moodboard_id,
            "original_concept": mb["concept"],
            "new_concept": new_concept,
            "mood_spec": original_spec.to_dict(),
            "note": f"MOOD_SPEC de '{mb['concept']}' — listo para generar '{new_concept}'",
        }
