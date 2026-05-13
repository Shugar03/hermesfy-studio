import { useStudioStore } from '../../stores/studioStore';

type Props = {
  onSend: () => void;
};

export function ChatPanel({ onSend }: Props) {
  const { turns, chatInput, setChatInput } = useStudioStore();

  return (
    <section className="panel" aria-label="Chat panel">
      <h3>Chat</h3>
      <div className="scroll" aria-live="polite">
        {turns.map((t) => (
          <div key={t.id} className="msg">
            <div><strong>You:</strong> {t.user_message}</div>
            <div><strong>Agent:</strong> {t.agent_response ?? '...'}</div>
          </div>
        ))}
      </div>
      <div className="row">
        <input
          aria-label="Message to agent"
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          placeholder="Ask agent to edit workflow..."
          onKeyDown={(e) => e.key === 'Enter' && onSend()}
        />
        <button onClick={onSend} aria-label="Send message">Send</button>
      </div>
    </section>
  );
}
