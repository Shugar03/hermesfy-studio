"""Parser for Hermes Agent verbose stdout output.

Hermes Agent can output "prose boxes" with structured thinking, tool calls,
actions, and final text. This parser extracts semantic events from raw stdout
for streaming into chat and canvas.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Event types parsed from stdout ────────────────────────────────────────────

@dataclass
class VerboseEvent:
    """A single event extracted from verbose Hermes stdout."""
    event_type: str  # thinking, text, tool_call, action, error, learning
    data: dict[str, Any] = field(default_factory=dict)
    raw_line: str = ""


KNOWN_EVENT_TYPE = str  # thinking | text | tool_call | action | error | done

# ── Regex patterns for Hermes verbose output ──────────────────────────────────

_RE_TOOL_CALL = re.compile(
    r'<tool_call>\s*\{.*"name":\s*"([^"]+)"\s*.*\}\s*</tool_call>',
    re.DOTALL,
)

_RE_TOOL_RESULT = re.compile(
    r'<tool_result>(.*?)</tool_result>',
    re.DOTALL,
)

_RE_THINKING = re.compile(
    r'<thinking>(.*?)</thinking>',
    re.DOTALL,
)

# Marker: Hermes's verbose prose box format
_RE_PROSE_START = re.compile(r'^──+\s*(.+?)\s*──+$')
_RE_LEARNING = re.compile(r'LEARNING_SAVED:\s*(.+)', re.IGNORECASE)

# Action taps from CLI
_RE_ACTION = re.compile(
    r'^(?:\[)?hermesfy\s+(create|connect|set|run|run-all|clear|save|load)\s',
    re.IGNORECASE,
)


class HermesVerboseParser:
    """Parses Hermes Agent verbose stdout into structured events.

    Handles:
    - Prose boxes (thinking sections)
    - Tool calls with JSON extraction
    - Action taps (hermesfy CLI commands)
    - Learnings saved
    - Raw text lines for streaming
    """

    def parse_line(self, line: str) -> Optional[VerboseEvent]:
        """Parse a single line of stdout. Returns an event or None if uninteresting."""
        line = line.strip()
        if not line:
            return None

        # ── Learning saved ──
        m = _RE_LEARNING.search(line)
        if m:
            return VerboseEvent(
                event_type="learning",
                data={"topic": m.group(1).strip()},
                raw_line=line,
            )

        # ── Prose box header ──
        m = _RE_PROSE_START.match(line)
        if m:
            return VerboseEvent(
                event_type="thinking",
                data={"header": m.group(1).strip()},
                raw_line=line,
            )

        # ── Tool call ──
        m = _RE_TOOL_CALL.search(line)
        if m:
            return VerboseEvent(
                event_type="tool_call",
                data={"tool_name": m.group(1), "raw": line},
                raw_line=line,
            )

        # ── Tool result ──
        m = _RE_TOOL_RESULT.search(line)
        if m:
            return VerboseEvent(
                event_type="tool_result",
                data={"result_text": m.group(1).strip()[:500]},
                raw_line=line,
            )

        # ── Action tap (CLI command) ──
        m = _RE_ACTION.search(line)
        if m:
            return VerboseEvent(
                event_type="action",
                data={"cli_command": m.group(1).strip(), "full": line},
                raw_line=line,
            )

        # ── Fall through: raw text ──
        return VerboseEvent(
            event_type="text",
            data={"content": line},
            raw_line=line,
        )

    def parse_stream(self, stdout: str) -> list[VerboseEvent]:
        """Parse entire stdout into a list of events."""
        events: list[VerboseEvent] = []
        for line in stdout.split("\n"):
            ev = self.parse_line(line)
            if ev:
                events.append(ev)
        return events

    def has_only_actions(self, events: list[VerboseEvent]) -> bool:
        """Return True if the output has tool/action events but no text."""
        has_text = any(e.event_type == "text" for e in events)
        has_actions = any(e.event_type in ("tool_call", "action")
                         for e in events)
        return has_actions and not has_text

    def extract_actions_summary(self, events: list[VerboseEvent]) -> list[str]:
        """Extract a human-readable summary of actions performed."""
        actions: list[str] = []
        for ev in events:
            if ev.event_type == "action":
                actions.append(ev.data.get("full", ev.raw_line))
            elif ev.event_type == "tool_call":
                actions.append(f"🔧 called {ev.data.get('tool_name', 'unknown')}")
        return actions
