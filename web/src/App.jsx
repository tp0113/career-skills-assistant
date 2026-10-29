import { useEffect, useState } from "react";
import { getEmployees, sendConfirm, sendMessage } from "./api.js";
import EmployeePicker from "./EmployeePicker.jsx";
import ChatLog from "./ChatLog.jsx";
import MessageInput from "./MessageInput.jsx";
import SuggestedPrompts from "./SuggestedPrompts.jsx";
import MetricsLine from "./MetricsLine.jsx";

const newConversationId = () => crypto.randomUUID().slice(0, 8);

export default function App() {
  const [employees, setEmployees] = useState([]);
  const [employeeId, setEmployeeId] = useState("");
  const [conversationId, setConversationId] = useState(newConversationId);
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    getEmployees()
      .then((list) => {
        setEmployees(list);
        if (list.length) setEmployeeId(list[0].id);
      })
      .catch((error) => setMessages([{ role: "error", text: error.message }]));
  }, []);

  // Switching employee starts a new conversation, matching the server's per-employee threads.
  function switchEmployee(id) {
    setEmployeeId(id);
    setConversationId(newConversationId());
    setMessages([]);
    setMetrics(null);
  }

  function addReply(result) {
    setMetrics(result.metrics);
    setMessages((old) => [
      ...old.map((m) => (m.pending ? { ...m, pending: null } : m)),
      {
        role: "assistant",
        text: result.reply,
        recommendation: result.recommendation,
        flagged: result.flagged,
        pending: result.pending_enrollment,
      },
    ]);
  }

  async function run(action) {
    setBusy(true);
    try {
      addReply(await action());
    } catch (error) {
      setMessages((old) => [...old, { role: "error", text: error.message }]);
    } finally {
      setBusy(false);
      setStatus("");
    }
  }

  function send(text) {
    if (!text.trim() || busy || !employeeId) return;
    setMessages((old) => [...old, { role: "user", text }]);
    run(() =>
      sendMessage(
        { employee_id: employeeId, conversation_id: conversationId, message: text },
        (tool) => setStatus(`calling ${tool}...`),
      ),
    );
  }

  function answer(confirm, courseId) {
    setMessages((old) => [...old, { role: "user", text: confirm ? "Confirm" : "Decline" }]);
    setStatus("saving your answer...");
    run(() =>
      sendConfirm({ employee_id: employeeId, conversation_id: conversationId, confirm, course_id: courseId }),
    );
  }

  return (
    <div className="app">
      <header>
        <h1>Career skills assistant</h1>
        <EmployeePicker employees={employees} value={employeeId} onChange={switchEmployee} disabled={busy} />
      </header>
      <ChatLog messages={messages} busy={busy} status={status} onAnswer={answer} />
      <MetricsLine metrics={metrics} />
      <SuggestedPrompts onPick={send} disabled={busy} />
      <MessageInput onSend={send} disabled={busy} />
    </div>
  );
}
