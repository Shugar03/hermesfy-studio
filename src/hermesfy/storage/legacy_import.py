"""Legacy workflow import — reads JSON workflows from ~/.hermes/hermesfy/workflows/."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from hermesfy.dag.graph import Node, NodeType, Edge, Workflow
from hermesfy.api.schemas import WorkflowV2, NodeV2, EdgeV2

logger = logging.getLogger("hermesfy.storage.legacy_import")

_LEGACY_DIR = Path.home() / ".hermes" / "hermesfy" / "workflows"


async def import_legacy_workflows(data_dir: str) -> list[WorkflowV2]:
    """Import legacy JSON workflows into V2 format.

    Converts V1 Workflow objects to WorkflowV2 with ports.
    Nodes use schema_version=1. Edges default to kind='data' with no ports.
    """
    imported: list[WorkflowV2] = []
    if not _LEGACY_DIR.exists():
        logger.info("No legacy workflows directory at %s", _LEGACY_DIR)
        return imported

    for fp in sorted(_LEGACY_DIR.glob("*.json")):
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)

            nodes_v2 = []
            for n in data.get("nodes", []):
                nodes_v2.append(NodeV2(
                    id=n["id"],
                    type=n["type"],
                    config=n.get("config", {}),
                    position={"x": n.get("position", [0, 0])[0], "y": n.get("position", [0, 0])[1]},
                    schema_version=1,
                ))

            edges_v2 = []
            for e in data.get("edges", []):
                edges_v2.append(EdgeV2(
                    id=f"{e['source']}->{e['target']}",
                    source=e["source"],
                    target=e["target"],
                    kind="data",
                ))

            wf = WorkflowV2(
                id=data.get("id", fp.stem),
                name=data.get("name", fp.stem),
                version=1,
                nodes=nodes_v2,
                edges=edges_v2,
            )
            imported.append(wf)
            logger.info("Imported legacy workflow %s (%d nodes, %d edges)",
                         wf.name, len(nodes_v2), len(edges_v2))
        except Exception:
            logger.exception("Failed to import legacy workflow %s", fp)

    logger.info("Imported %d legacy workflows", len(imported))
    return imported
