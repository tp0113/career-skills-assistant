import { useEffect, useState } from "react";
import { getEmployees, getHealth, getProfile, sendConfirm, sendMessage } from "./api.js";
import EmployeePicker from "./EmployeePicker.jsx";
import ChatLog from "./ChatLog.jsx";
import MessageInput from "./MessageInput.jsx";
import SuggestedPrompts from "./SuggestedPrompts.jsx";
import ProfileCard from "./ProfileCard.jsx";

const newConversationId = () => crypto.randomUUID().slice(0, 8);

export default function App() {
  const [employees, setEmployees] = useState([]);
  const [employeeId, setEmployeeId] = useState("");
  const [conversationId, setConversationId] = useState(newConversationId);
  const [messages, setMessages] = useState([]);
  const [steps, setSteps] = useState([]);
  const [busy, setBusy] = useState(false);
  const [profile, setProfile] = useState(null);
  const [model, setModel] = useState("");

  useEffect(() => {
    getEmployees()
      .then((list) => {
        setEmployees(list);
        if (list.length) setEmployeeId(list[0].id);
      })
      .catch((error) => setMessages([{ role: "error", text: error.message }]));
    getHealth()
      .then((health) => setModel(health.model))
      .catch(() => setModel(""));
  }, []);

  // The sidebar reloads on sign-in and after every reply, so a new enrollment shows up there at once.
  function refreshProfile(id = employeeId) {
    if (!id) return;
    getProfile(id)
      .then(setProfile)
      .catch(() => setProfile(null));
  }
  useEffect(() => {
    refreshProfile(employeeId);
  }, [employeeId]);

  // Switching employee starts a new conversation, matching the server's per-employee threads.
  function switchEmployee(id) {
    setEmployeeId(id);
    setConversationId(newConversationId());
    setMessages([]);
    setProfile(null);
  }

  function addReply(result) {
    setMessages((old) => [
      ...old.map((m) => (m.pending ? { ...m, pending: null } : m)),
      {
        role: "assistant",
        text: result.reply,
        recommendation: result.recommendation,
        flagged: result.flagged,
        pending: result.pending_enrollment,
        metrics: result.metrics,
      },
    ]);
  }

  async function run(action) {
    setBusy(true);
    setSteps([]);
    try {
      addReply(await action());
    } catch (error) {
      setMessages((old) => [...old, { role: "error", text: error.message }]);
    } finally {
      setBusy(false);
      setSteps([]);
      refreshProfile();
    }
  }

  function send(text) {
    if (!text.trim() || busy || !employeeId) return;
    setMessages((old) => [...old, { role: "user", text }]);
    run(() =>
      sendMessage({ employee_id: employeeId, conversation_id: conversationId, message: text }, (tool) =>
        setSteps((old) => (old.includes(tool) ? old : [...old, tool])),
      ),
    );
  }

  function answer(confirm, courseId) {
    setMessages((old) => [...old, { role: "user", text: confirm ? "Confirm" : "Decline" }]);
    setSteps(["saving"]);
    run(() =>
      sendConfirm({ employee_id: employeeId, conversation_id: conversationId, confirm, course_id: courseId }),
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">◆</span>
          <div>
            <h1>Career skills assistant</h1>
            <p className="subtitle">Skills, courses and roles from your own profile</p>
          </div>
        </div>
        <div className="topbar-right">
          {model && <span className="model-chip">{model} · runs locally</span>}
          <EmployeePicker employees={employees} value={employeeId} onChange={switchEmployee} disabled={busy} />
        </div>
      </header>
      <div className="layout">
        <aside className="sidebar">
          <ProfileCard profile={profile} />
        </aside>
        <section className="chat">
          <ChatLog messages={messages} busy={busy} steps={steps} onAnswer={answer} />
          <SuggestedPrompts onPick={send} disabled={busy} />
          <MessageInput onSend={send} disabled={busy} />
        </section>
      </div>
    </div>
  );
}
