"""Curator — descarga, filtra y puntúa imágenes para moodboard.

Pipeline:
1. Descarga imágenes (con timeout + headers correctos)
2. Filtra por resolución mínima
3. Deduplica por hash perceptual
4. Filtra por diversidad (máximo N del mismo pinner/alt)
5. Ordena por score
6. Guarda en la carpeta del moodboard
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests as req
from PIL import Image

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False

logger = logging.getLogger("hermesfy.moodboard.curator")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Referer": "https://www.pinterest.com/",
}
MIN_FILE_SIZE = 5000  # 5KB mínimo
MIN_DIMENSION = 300   # 300px mínimo en cualquier eje
TIMEOUT = 15


def download_image(url: str, output_path: str | Path) -> dict | None:
    """Descarga una imagen y devuelve metadata, o None si falla."""
    try:
        resp = req.get(url, timeout=TIMEOUT, headers=HEADERS, stream=True)
        if resp.status_code != 200:
            logger.debug("HTTP %d for %s", resp.status_code, url)
            return None

        content = resp.content
        if len(content) < MIN_FILE_SIZE:
            logger.debug("Too small (%d bytes): %s", len(content), url)
            return None

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(content)

        # Verificar dimensiones
        try:
            with Image.open(output_path) as img:
                w, h = img.size
                if w < MIN_DIMENSION and h < MIN_DIMENSION:
                    os.remove(output_path)
                    logger.debug("Too small (%dx%d): %s", w, h, url)
                    return None
        except Exception:
            os.remove(output_path)
            logger.debug("Invalid image: %s", url)
            return None

        return {
            "path": str(output_path),
            "size_kb": len(content) // 1024,
            "width": w,
            "height": h,
        }
    except Exception as e:
        logger.debug("Download failed %s: %s", url, e)
        return None


def compute_phash(image_path: str | Path) -> str | None:
    """Hash perceptual de una imagen."""
    if not HAS_IMAGEHASH:
        return None
    try:
        with Image.open(image_path) as img:
            h = imagehash.phash(img)
            return str(h)
    except Exception:
        return None


def curate_images(
    candidates: list[dict],
    output_dir: str | Path,
    concept: str = "",
    max_images: int = 15,
    max_per_group: int = 3,
) -> list[dict]:
    """Pipeline completo de curaduría.

    Args:
        candidates: [{url, alt, score}, ...] desde el searcher
        output_dir: Carpeta donde guardar las imágenes
        concept: Concepto para naming de archivos
        max_images: Máximo de imágenes a devolver
        max_per_group: Máximo de imágenes del mismo alt text

    Returns:
        Lista de metadatos de imágenes curadas [{path, size_kb, phash, ...}]
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    concept_slug = re.sub(r'[^a-z0-9]', '_', concept.lower())[:20] if concept else "img"

    # Ordenar por score descendente
    sorted_candidates = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)

    # Filtro de diversidad: agrupar por alt text similar
    alt_groups: dict[str, list[dict]] = {}
    for c in sorted_candidates:
        key = c.get("alt", "")[:30].lower()  # Primeros 30 chars como grupo
        if key not in alt_groups:
            alt_groups[key] = []
        alt_groups[key].append(c)

    # Tomar máximo N por grupo
    diverse = []
    for key, group in alt_groups.items():
        diverse.extend(group[:max_per_group])

    # Reordenar por score después del filtro
    diverse.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Descargar
    curated = []
    seen_hashes = set()

    for i, candidate in enumerate(diverse[:max_images]):
        url = candidate["url"]
        alt = candidate.get("alt", "")[:30]
        alt_slug = re.sub(r'[^a-zA-Z0-9_-]', '', alt.replace(" ", "_"))[:30] or f"{concept_slug}_{i}"
        ext = url.split(".")[-1] if "." in url else "jpg"
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        fname = f"{i+1:02d}_{alt_slug}.{ext}"
        fpath = output_dir / fname

        meta = download_image(url, fpath)
        if not meta:
            continue

        # Dedup por hash perceptual
        phash = compute_phash(fpath)
        if phash:
            if phash in seen_hashes:
                os.remove(fpath)
                logger.debug("Duplicate (phash) removed: %s", fname)
                continue
            seen_hashes.add(phash)

        meta["fname"] = fname
        meta["alt"] = candidate.get("alt", "")
        meta["url"] = url
        meta["score"] = candidate.get("score", 0)
        curated.append(meta)
        logger.info("  ✓ %s — %dKB (%dx%d) score=%d", fname, meta["size_kb"], meta.get("width", 0), meta.get("height", 0), meta["score"])

    return curated
