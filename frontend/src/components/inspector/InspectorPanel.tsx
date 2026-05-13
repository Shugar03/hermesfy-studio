import { useMemo } from 'react';
import { useStudioStore } from '../../stores/studioStore';

export function InspectorPanel() {
  const { workflow, selectedNodeId } = useStudioStore();

  const selectedNode = useMemo(() => {
    if (!workflow || !selectedNodeId) return null;
    return workflow.nodes.find((n) => n.id === selectedNodeId) ?? null;
  }, [workflow, selectedNodeId]);

  return (
    <section className="panel">
      <h3>Inspector</h3>
      {!selectedNode ? (
        <p>Select a node in the canvas.</p>
      ) : (
        <>
          <p><strong>ID:</strong> {selectedNode.id}</p>
          <p><strong>Type:</strong> {selectedNode.type}</p>
          <p><strong>Position:</strong> {selectedNode.position.x}, {selectedNode.position.y}</p>
          <h4>Config</h4>
          <pre>{JSON.stringify(selectedNode.config, null, 2)}</pre>
        </>
      )}
    </section>
  );
}
