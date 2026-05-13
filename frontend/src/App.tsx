import { useCallback, useRef, useState } from 'react';
import './App.css';
import { ApiClient } from './lib/apiClient';
import { connectWs } from './lib/wsClient';
import { ChatPanel } from './components/chat/ChatPanel';
import { LiveCanvas } from './components/canvas/LiveCanvas';
import { InspectorPanel } from './components/inspector/InspectorPanel';
import { EventFeed } from './components/approvals/EventFeed';
import { TopBar } from './components/layout/TopBar';
import { useStudioStore } from './stores/studioStore';

function App() {
  const {
    baseUrl,
    workflowId,
    sessionId,
    authToken,
    chatInput,
    setSessionId,
    setWorkflowId,
    setWorkflow,
    addTurn,
    addEvent,
    setWsState,
  } = useStudioStore();

  const [error, setError] = useState<string>('');
  const disconnectRef = useRef<(() => void) | null>(null);

  const api = new ApiClient(baseUrl, authToken);

  const onLoadWorkflow = useCallback(async () => {
    try {
      setError('');
      if (!workflowId) return;
      const wf = await api.getWorkflow(workflowId);
      setWorkflow(wf);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed loading workflow');
    }
  }, [api, workflowId, setWorkflow]);

  const onCreateSession = useCallback(async () => {
    try {
      setError('');
      const s = await api.createSession('Hermesfy V5 Session', workflowId || undefined);
      setSessionId(s.id);
      if (!workflowId && s.workflow_id) setWorkflowId(s.workflow_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed creating session');
    }
  }, [api, setSessionId, workflowId, setWorkflowId]);

  const onSend = useCallback(async () => {
    try {
      setError('');
      const message = chatInput.trim();
      if (!message) return;

      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const s = await api.createSession('Hermesfy V5 Session', workflowId || undefined);
        currentSessionId = s.id;
        setSessionId(s.id);
        if (!workflowId && s.workflow_id) setWorkflowId(s.workflow_id);
      }

      const turn = await api.sendMessage(currentSessionId, message);
      addTurn(turn);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed sending message');
    }
  }, [api, sessionId, workflowId, chatInput, addTurn, setSessionId, setWorkflowId]);

  const onConnectWs = useCallback(() => {
    disconnectRef.current?.();
    setError('');

    const cleanups: Array<() => void> = [];

    if (sessionId) {
      cleanups.push(
        connectWs(
          `${baseUrl.replace('http', 'ws')}/ws/chat/${sessionId}`,
          addEvent,
          (s) => setWsState(s),
        ),
      );
    }

    if (workflowId) {
      cleanups.push(
        connectWs(
          `${baseUrl.replace('http', 'ws')}/ws/dag/${workflowId}`,
          addEvent,
          (s) => setWsState(s),
        ),
      );
    }

    disconnectRef.current = () => cleanups.forEach((c) => c());
  }, [sessionId, workflowId, baseUrl, addEvent, setWsState]);

  return (
    <main className="app">
      <TopBar onLoadWorkflow={onLoadWorkflow} onCreateSession={onCreateSession} onConnectWs={onConnectWs} />
      {error && <div className="errorBanner" role="alert">{error}</div>}

      <section className="grid">
        <div className="col left">
          <ChatPanel onSend={onSend} />
          <EventFeed />
        </div>

        <div className="col center">
          <LiveCanvas />
        </div>

        <div className="col right">
          <InspectorPanel />
        </div>
      </section>
    </main>
  );
}

export default App;
