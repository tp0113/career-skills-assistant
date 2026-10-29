import { useEffect, useRef } from "react";
import RecommendationCards from "./RecommendationCards.jsx";
import EnrollConfirm from "./EnrollConfirm.jsx";
import MetricsLine from "./MetricsLine.jsx";
import ReplyTag from "./ReplyTag.jsx";
import WorkingSteps from "./WorkingSteps.jsx";

export default function ChatLog({ messages, busy, steps, onAnswer }) {
  const end = useRef(null);
  // Braces matter: an effect may only return a cleanup function, and Chrome's scrollIntoView now returns a
  // Promise. Returned, React called it as the cleanup on the next message and the page went white.
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, steps, busy]);

  return (
    <main className="log" aria-live="polite">
      {messages.length === 0 && (
        <div className="empty">
          <p className="empty-title">Ask about your next career step</p>
          <p>Pick a question below or type your own. Answers use only your own profile.</p>
        </div>
      )}
      {messages.map((m, i) => (
        <div key={i} className={`bubble ${m.role}`}>
          {m.role === "assistant" && <ReplyTag metrics={m.metrics} />}
          {/* The cards show the whole recommendation, so its text version is not repeated. */}
          {!m.recommendation && <p className="text">{m.text}</p>}
          {m.flagged?.length > 0 && (
            <p className="note">Skipped as unsafe: {m.flagged.map((f) => f.id).join(", ")}</p>
          )}
          <RecommendationCards recommendation={m.recommendation} />
          {m.pending && <EnrollConfirm pending={m.pending} disabled={busy} onAnswer={onAnswer} />}
          {m.role === "assistant" && <MetricsLine metrics={m.metrics} />}
        </div>
      ))}
      {busy && <WorkingSteps steps={steps} />}
      <div ref={end} />
    </main>
  );
}
