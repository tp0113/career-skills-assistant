const PROMPTS = [
  "What skills should I develop for my next career opportunity?",
  "What are Marcus's skills?",
  "Enroll me in the first course",
];

export default function SuggestedPrompts({ onPick, disabled }) {
  return (
    <div className="prompts">
      {PROMPTS.map((p) => (
        <button key={p} className="secondary" disabled={disabled} onClick={() => onPick(p)}>
          {p}
        </button>
      ))}
    </div>
  );
}
