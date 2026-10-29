const PROMPTS = [
  "What skills should I develop for my next career opportunity?",
  "Which skills am I missing?",
  "What are Marcus's skills?",
  "Enroll me in the first course",
];

export default function SuggestedPrompts({ onPick, disabled }) {
  return (
    <div className="prompts">
      {PROMPTS.map((p) => (
        <button key={p} className="prompt" disabled={disabled} onClick={() => onPick(p)}>
          {p}
        </button>
      ))}
    </div>
  );
}
