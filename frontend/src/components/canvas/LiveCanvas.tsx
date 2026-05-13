import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from 'reactflow';
import 'reactflow/dist/style.css';
import { useMemo } from 'react';
import { useStudioStore } from '../../stores/studioStore';

export function LiveCanvas() {
  const { workflow, selectedNodeId, setSelectedNodeId } = useStudioStore();

  const nodes = useMemo<Node[]>(() => {
    if (!workflow) return [];
    return workflow.nodes.map((n) => ({
      id: n.id,
      type: 'default',
      position: n.position,
      data: { label: `${n.type}\n${n.id}` },
      selected: selectedNodeId === n.id,
    }));
  }, [workflow, selectedNodeId]);

  const edges = useMemo<Edge[]>(() => {
    if (!workflow) return [];
    return workflow.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.kind ?? 'data',
      sourceHandle: e.source_port ?? undefined,
      targetHandle: e.target_port ?? undefined,
    }));
  }, [workflow]);

  return (
    <section className="panel canvas">
      <h3>Live Canvas</h3>
      <div className="canvasInner">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          onNodeClick={(_, n) => setSelectedNodeId(n.id)}
        >
          <Background />
          <MiniMap />
          <Controls />
        </ReactFlow>
      </div>
    </section>
  );
}
