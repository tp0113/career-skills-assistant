import { useEffect, useRef } from "react";
import RecommendationCards from "./RecommendationCards.jsx";
import EnrollConfirm from "./EnrollConfirm.jsx";

export default function ChatLog({ messages, busy, status, onAnswer }) {
  const end = useRef(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [messages, status]);

  return (
    <main className="log" aria-live="polite">
      {messages.length === 0 && <p className="hint">Pick a question below or type your own.</p>}
      {messages.map((m, i) => (
        <div key={i} className={`bubble ${m.role}`}>
          {/* The cards show the whole recommendation, so its text version is not repeated. */}
          {!m.recommendation && <p>{m.text}</p>}
          {m.flagged?.length > 0 && (
            <p className="note">Skipped as unsafe: {m.flagged.map((f) => f.id).join(", ")}</p>
          )}
          <RecommendationCards recommendation={m.recommendation} />
          {m.pending && <EnrollConfirm pending={m.pending} disabled={busy} onAnswer={onAnswer} />}
        </div>
      ))}
      {busy && <div className="bubble status">{status || "thinking..."}</div>}
      <div ref={end} />
    </main>
  );
}
