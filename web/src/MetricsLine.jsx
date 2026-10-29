export default function MetricsLine({ metrics }) {
  if (!metrics) return <p className="metrics" />;
  return (
    <p className="metrics">
      {metrics.seconds}s · {metrics.model_calls} model calls · {metrics.prompt_tokens} prompt tokens ·{" "}
      {metrics.output_tokens} output tokens
      {metrics.repair_attempts > 0 && ` · ${metrics.repair_attempts} repairs`}
    </p>
  );
}
