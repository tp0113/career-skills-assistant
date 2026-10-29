import { useEffect, useRef, useState } from "react";

export default function MessageInput({ onSend, disabled }) {
  const [text, setText] = useState("");
  const input = useRef(null);
  // Back in the box as soon as a reply lands, so the next question can be typed right away.
  useEffect(() => {
    if (!disabled) input.current?.focus();
  }, [disabled]);

  function submit(event) {
    event.preventDefault();
    onSend(text);
    setText("");
  }
  return (
    <form className="input" onSubmit={submit}>
      <input ref={input} value={text} onChange={(e) => setText(e.target.value)} maxLength={1000}
             disabled={disabled} placeholder="Ask about your skills, courses or roles" />
      <button disabled={disabled || !text.trim()}>Send</button>
    </form>
  );
}
