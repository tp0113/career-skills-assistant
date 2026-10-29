// The cost of one reply, as small chips under it. Same figures as the request log line.
export default function MetricsLine({ metrics }) {
  if (!metrics) return null;
  const chips = [
    `⏱ ${metrics.seconds}s`,
    `${metrics.model_calls} model call${metrics.model_calls === 1 ? "" : "s"}`,
  ];
  if (metrics.model_calls > 0) chips.push(`${metrics.prompt_tokens} in · ${metrics.output_tokens} out tokens`);
  if (metrics.repair_attempts > 0) chips.push(`${metrics.repair_attempts} repair${metrics.repair_attempts === 1 ? "" : "s"}`);
  return (
    <div className="metrics">
      {chips.map((chip) => (
        <span className="metric" key={chip}>{chip}</span>
      ))}
    </div>
  );
}
