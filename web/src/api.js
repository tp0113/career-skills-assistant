// Thin wrappers over the routes the UI uses. Errors become plain messages.
async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`The server answered ${response.status}`);
  return response;
}

export async function getEmployees() {
  const response = await fetch("/api/employees");
  if (!response.ok) throw new Error(`The server answered ${response.status}`);
  return response.json();
}

// Reads the NDJSON stream: onStatus(toolName) for each tool call, resolves with the final result.
export async function sendMessage(body, onStatus) {
  const response = await post("/api/chat/stream", body);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;
  const handle = (line) => {
    if (!line.trim()) return;
    const item = JSON.parse(line);
    if (item.type === "status") onStatus(item.tool);
    else if (item.type === "result") result = item;
    else if (item.type === "error") throw new Error(item.detail);
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    lines.forEach(handle);
  }
  handle(buffer);
  if (!result) throw new Error("The server closed the stream without an answer");
  return result;
}

export async function sendConfirm(body) {
  return (await post("/api/confirm", body)).json();
}
