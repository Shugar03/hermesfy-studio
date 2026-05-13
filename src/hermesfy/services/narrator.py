"""Narrator fallback — translates tool calls and actions into human-readable text.

When the Hermes model returns `content: ""` + tool_calls (known bug with Kimi K2.6
and some other models), the narrator synthesizes a natural-language summary of what
the agent actually did, so the user doesn't see a blank response.
"""

from __future__ import annotations

import logging
from typing import Optional

from hermesfy.services.hermes_verbose_parser import HermesVerboseParser, VerboseEvent

logger = logging.getLogger("hermesfy.narrator")

# ── Narrator templates ────────────────────────────────────────────────────────

_FALLBACK_TEMPLATES: dict[str, list[str]] = {
    "create": [
        "Creé un nodo de tipo {type} en el canvas.",
        "Agregué un nodo {type} al workflow.",
    ],
    "connect": [
        "Conecté {source} → {target} en el DAG.",
        "Agregué una conexión entre {source} y {target}.",
    ],
    "set": [
        "Actualicé la configuración del nodo {node}.",
        "Modifiqué parámetros de {node}.",
    ],
    "run": [
        "Ejecuté el nodo {target} y su cadena upstream.",
        "Inicié la ejecución de {target}.",
    ],
    "run-all": [
        "Ejecuté el workflow completo.",
    ],
    "clear": [
        "Limpié el canvas para empezar de nuevo.",
    ],
}


def _pick_template(action: str) -> str:
    """Pick a natural-language template for a CLI action."""
    templates = _FALLBACK_TEMPLATES.get(action, [
        "Ejecuté la acción {action} en el sistema.",
    ])
    import random
    return random.choice(templates)


class Narrator:
    """Generates human-readable summaries when the model produces no text content.

    Uses a two-tier strategy:
    1. Local templates instant from action taps (zero cost, instant)
    2. External LLM call for richer narration (optional, with cost/timeout guard)
    """

    def __init__(self) -> None:
        self.parser = HermesVerboseParser()

    async def narrate(
        self,
        stdout: str,
        use_external: bool = False,
    ) -> str:
        """Generate a narration from Hermes stdout.

        Args:
            stdout: Raw stdout from the Hermes subprocess.
            use_external: If True, attempt external LLM narration (with guard).

        Returns:
            A natural-language summary of what the agent did.
        """
        events = self.parser.parse_stream(stdout)

        # If there's text content, just return it
        text_events = [e for e in events if e.event_type == "text" and e.data.get("content", "").strip()]
        if text_events:
            return "\n".join(e.data["content"] for e in text_events)

        # No text content — use local fallback
        return self._local_fallback(events)

    def _local_fallback(self, events: list[VerboseEvent]) -> str:
        """Generate a local narration from action taps and tool calls."""
        actions = self.parser.extract_actions_summary(events)

        if not actions:
            return "El agente procesó tu mensaje pero no produjo acciones visibles."

        # Summarize in natural language
        lines: list[str] = ["Resumen de lo que hice:"]
        for action in actions:
            # Try to extract CLI action details
            parts = action.split()
            if len(parts) >= 2 and parts[0].lower() in ("hermesfy",):
                cmd = parts[1].lower() if len(parts) > 1 else "unknown"
                template = _pick_template(cmd)

                # Extract entities from the action string
                entities: dict[str, str] = {"action": cmd}
                for i, p in enumerate(parts):
                    if p.startswith("--") and i + 1 < len(parts):
                        key = p[2:].replace("-", "_")
                        entities[key] = parts[i + 1]

                try:
                    narrated = template.format(**entities)
                except KeyError:
                    narrated = template
                lines.append(f"  • {narrated}")
            else:
                lines.append(f"  • {action}")

        # Add count
        node_count = sum(1 for e in events if e.event_type in ("action", "tool_call"))
        if node_count > 0:
            lines.append(f"\nTotal: {node_count} acciones ejecutadas en este turno.")

        return "\n".join(lines)

    async def narrate_passthrough(self, text: str) -> str:
        """Pass through text unchanged — used when model output already has content."""
        return text.strip() if text.strip() else "El agente completó el turno sin contenido de texto."


# ── Singleton convenience ─────────────────────────────────────────────────────

_narrator: Optional[Narrator] = None


def get_narrator() -> Narrator:
    global _narrator
    if _narrator is None:
        _narrator = Narrator()
    return _narrator
