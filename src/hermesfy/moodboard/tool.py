"""Tool handler for hermesfy_moodboard."""
from __future__ import annotations

import json
import logging
from typing import Any

from hermesfy.moodboard.orchestrator import MoodboardOrchestrator
from hermesfy.moodboard.database import MoodboardDB

logger = logging.getLogger("hermesfy.moodboard.tool")

MOODBOARD_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "run",       # Pipeline completo
                "board",     # Scrapear board + analizar
                "search",    # Solo buscar imágenes
                "list",      # Listar moodboards
                "get",       # Ver moodboard por ID
                "stats",     # Estadísticas
                "use",       # Reusar moodboard
            ],
            "description": "Acción a ejecutar",
        },
        "concept": {
            "type": "string",
            "description": "Concepto: 'hotel lujo selva'",
        },
        "format": {
            "type": "string",
            "enum": ["default", "advertising", "editorial", "social_media", "product", "hospitality", "fashion"],
            "default": "default",
            "description": "Formato o categoría visual",
        },
        "source": {
            "type": "string",
            "enum": ["pinterest_search", "pinterest_board", "brave"],
            "default": "pinterest_search",
            "description": "Fuente de imágenes",
        },
        "source_url": {
            "type": "string",
            "description": "URL del board de Pinterest (si source='pinterest_board')",
        },
        "brand": {
            "type": "string",
            "description": "Nombre de marca para aplicar DESIGN.md: 'provincial-plaza'",
        },
        "tags": {
            "type": "string",
            "description": "Tags CSV opcionales: 'hotel, lujo, salta'",
        },
        "moodboard_id": {
            "type": "string",
            "description": "ID de moodboard existente (para 'get' y 'use')",
        },
        "new_concept": {
            "type": "string",
            "description": "Nuevo concepto para reciclar moodboard (con 'use')",
        },
        "limit": {
            "type": "integer",
            "default": 10,
            "description": "Límite de resultados (list)",
        },
        "query": {
            "type": "string",
            "description": "Búsqueda textual (search/list con query)",
        },
    },
    "required": ["action"],
}


async def moodboard_handler(args: dict, ctx=None) -> str:
    """Handler para la herramienta hermesfy_moodboard."""
    action = args.get("action", "run")
    orchestrator = MoodboardOrchestrator()
    db = MoodboardDB()

    try:
        if action == "run":
            result = orchestrator.run_pipeline(
                concept=args.get("concept", ""),
                format=args.get("format", "default"),
                source=args.get("source", "pinterest_search"),
                source_url=args.get("source_url"),
                brand=args.get("brand"),
                tags=args.get("tags"),
            )
            if "error" in result:
                return f"❌ {result['error']}"
            return _format_result(result)

        elif action == "board":
            url = args.get("source_url")
            if not url:
                return "❌ Necesito 'source_url' con el link del board"
            result = orchestrator.run_pipeline(
                concept=args.get("concept", "moodboard"),
                source="pinterest_board",
                source_url=url,
                brand=args.get("brand"),
            )
            if "error" in result:
                return f"❌ {result['error']}"
            return _format_result(result)

        elif action == "search":
            # Solo búsqueda, sin análisis completo
            from hermesfy.moodboard.searcher import search_moodboard_sources
            candidates = search_moodboard_sources(
                concept=args.get("concept", ""),
                format=args.get("format", "default"),
                source=args.get("source", "pinterest_search"),
                source_url=args.get("source_url"),
                max_images=20,
            )
            if not candidates:
                return "❌ No se encontraron imágenes"
            lines = [f"🔍 **{args.get('concept')}** — {len(candidates)} candidatos\n"]
            for c in candidates[:15]:
                score = c.get("score", 0)
                alt = c.get("alt", "")[:60]
                lines.append(f"  `[{score:02d}]` {alt}")
                lines.append(f"         {c['url'][:90]}")
            return "\n".join(lines)

        elif action == "list":
            results = db.list_moodboards(
                limit=args.get("limit", 10),
                brand=args.get("brand"),
            )
            if not results:
                return "📭 No hay moodboards guardados"
            lines = ["📋 **Moodboards guardados:**\n"]
            for r in results:
                used = r.get("used_in_generations", 0)
                lines.append(
                    f"  `{r['id']}` | {r['concept'][:30]} | "
                    f"{r['image_count']} img | usado {used}x | "
                    f"`{r['status']}`"
                )
            return "\n".join(lines)

        elif action == "get":
            mb_id = args.get("moodboard_id")
            if not mb_id:
                return "❌ Necesito 'moodboard_id'"
            mb = db.get_moodboard(mb_id)
            if not mb:
                return f"❌ Moodboard `{mb_id}` no encontrado"
            # Devolver preview si existe
            if mb.get("mood_spec_md"):
                return mb["mood_spec_md"]
            return (f"📌 **{mb['concept']}** (`{mb['id']}`)\n"
                    f"  Fuente: {mb['source']} · {mb['image_count']} imágenes\n"
                    f"  Estado: `{mb['status']}` · Marca: {mb.get('brand', '—')}")

        elif action == "stats":
            stats = db.get_stats()
            lines = ["📊 **Estadísticas de Moodboard:**\n"]
            for k, v in stats.items():
                if isinstance(v, dict):
                    lines.append(f"  • {k}:")
                    for sk, sv in v.items():
                        lines.append(f"    - {sk}: {sv}")
                else:
                    lines.append(f"  • {k}: {v}")
            return "\n".join(lines)

        elif action == "use":
            mb_id = args.get("moodboard_id")
            new_concept = args.get("new_concept")
            if not mb_id:
                return "❌ Necesito 'moodboard_id'"
            result = orchestrator.regenerate(mb_id, new_concept or "", args.get("brand"))
            if result is None:
                return f"❌ Moodboard `{mb_id}` no encontrado o sin MOOD_SPEC"
            lines = [f"♻️ **Reusando** `{mb_id}` ({result['original_concept']})\n"]
            lines.append(f"  Nuevo concepto: **{result['new_concept'] or '—'}**")
            lines.append(f"  {result['note']}")
            if result.get("mood_spec", {}).get("dominant_palette"):
                palette = result["mood_spec"]["dominant_palette"]
                lines.append(f"\n  🎨 Paleta: {' '.join(palette)}")
                lines.append(f"  😌 Mood: {result['mood_spec'].get('mood_majority', '—')}")
            return "\n".join(lines)

        else:
            return f"❌ Acción desconocida: {action}"

    except Exception as e:
        logger.exception("Moodboard error")
        return f"❌ Error en moodboard: {e}"


def _format_result(result: dict) -> str:
    """Formatea el resultado del pipeline para mostrar al usuario."""
    lines = [
        f"🎨 **Moodboard creado:** `{result['moodboard_id']}`",
        f"  Concepto: {result['concept']}",
    ]
    if result.get("brand"):
        lines.append(f"  Marca: **{result['brand']}**")
    lines.append(f"  Imágenes: {result['image_count']}")
    lines.append("")

    # Preview del mood spec
    ms = result.get("mood_spec", {})
    if ms.get("dominant_palette"):
        palette_str = " · ".join(ms["dominant_palette"])
        lines.append(f"🎨 `{palette_str}`")
    if ms.get("mood_majority"):
        lines.append(f"😌 Mood: **{ms['mood_majority']}**")
    if ms.get("lighting_consensus"):
        lines.append(f"💡 Luz: {ms['lighting_consensus']}")
    if ms.get("composition_mode"):
        lines.append(f"📐 Composición: {ms['composition_mode']}")
    if ms.get("confidence"):
        pct = ms["confidence"] * 100
        lines.append(f"📊 Confianza: {pct:.0f}%")

    # Imágenes
    if result.get("images"):
        lines.append(f"\n📸 **{len(result['images'])} imágenes** en `{result['moodboard_id']}/`")
        # Mostrar algunas stats
        avg_score = sum(i.get("score", 0) for i in result["images"]) / len(result["images"])
        avg_size = sum(i.get("size_kb", 0) for i in result["images"]) / len(result["images"])
        lines.append(f"  Score promedio: {avg_score:.0f} · Tamaño: {avg_size:.0f}KB c/u")

    lines.append(f"\n💡 *Usá `moodboard use {result['moodboard_id']}` para reciclar*")

    return "\n".join(lines)
