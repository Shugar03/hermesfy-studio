import { useStudioStore } from '../../stores/studioStore';

export function EventFeed() {
  const { events } = useStudioStore();

  return (
    <section className="panel">
      <h3>Agent / WS Events</h3>
      <div className="scroll">
        {events.map((e) => (
          <div key={e.id + ':' + e.seq} className="event">
            <strong>{e.type}</strong> · seq {e.seq}
            <pre>{JSON.stringify(e.payload ?? {}, null, 2)}</pre>
          </div>
        ))}
      </div>
    </section>
  );
}
