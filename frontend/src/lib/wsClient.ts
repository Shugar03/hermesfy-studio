import type { WSEventEnvelope } from '../types';

type EventHandler = (event: WSEventEnvelope) => void;

export function connectWs(
  url: string,
  onEvent: EventHandler,
  onState?: (state: 'open' | 'closed' | 'error') => void,
): () => void {
  const ws = new WebSocket(url);

  ws.onopen = () => onState?.('open');
  ws.onerror = () => onState?.('error');
  ws.onclose = () => onState?.('closed');

  ws.onmessage = (msg) => {
    try {
      const parsed = JSON.parse(msg.data) as WSEventEnvelope;
      onEvent(parsed);
    } catch {
      // ignore malformed payloads
    }
  };

  return () => ws.close();
}
