import { useStudioStore } from '../../stores/studioStore';

type Props = {
  onLoadWorkflow: () => void;
  onCreateSession: () => void;
  onConnectWs: () => void;
};

export function TopBar({ onLoadWorkflow, onCreateSession, onConnectWs }: Props) {
  const {
    baseUrl,
    workflowId,
    sessionId,
    authToken,
    wsState,
    setBaseUrl,
    setWorkflowId,
    setSessionId,
    setAuthToken,
  } = useStudioStore();

  return (
    <header className="topbar" aria-label="Connection controls">
      <input
        aria-label="API base URL"
        value={baseUrl}
        onChange={(e) => setBaseUrl(e.target.value)}
        placeholder="Base URL"
      />
      <input
        aria-label="Workflow ID"
        value={workflowId}
        onChange={(e) => setWorkflowId(e.target.value)}
        placeholder="workflow_id"
      />
      <input
        aria-label="Session ID"
        value={sessionId}
        onChange={(e) => setSessionId(e.target.value)}
        placeholder="session_id"
      />
      <input
        aria-label="Auth token"
        value={authToken}
        onChange={(e) => setAuthToken(e.target.value)}
        placeholder="Bearer token (optional)"
      />
      <button onClick={onLoadWorkflow}>Load DAG</button>
      <button onClick={onCreateSession}>New Session</button>
      <button onClick={onConnectWs}>Connect WS</button>
      <span className={`pill ${wsState}`} aria-live="polite">WS: {wsState}</span>
    </header>
  );
}
