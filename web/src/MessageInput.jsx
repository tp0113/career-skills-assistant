import { useState } from "react";

export default function MessageInput({ onSend, disabled }) {
  const [text, setText] = useState("");
  function submit(event) {
    event.preventDefault();
    onSend(text);
    setText("");
  }
  return (
    <form className="input" onSubmit={submit}>
      <input value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} disabled={disabled}
             placeholder="Ask about your skills, courses or jobs" />
      <button disabled={disabled || !text.trim()}>Send</button>
    </form>
  );
}
