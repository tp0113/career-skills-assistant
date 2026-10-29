// A small tag that says how a reply was made, from the route and outcome the server reports.
// It makes the design visible: guards and data answers never call the model.
function tagFor(metrics) {
  const { route, outcome } = metrics;
  if (route === "refuse") return ["guard", "🛡 Privacy guard · model not called"];
  if (outcome === "out_of_scope") return ["data", "Off-topic · model not called"];
  if (["profile", "gaps", "followup"].includes(route)) return ["data", "From your data · model not called"];
  if (outcome === "enrolled") return ["success", "✓ Enrolled"];
  if (outcome === "enroll_pending") return ["enroll", "Enrollment · needs your confirm"];
  if (route === "enroll" || outcome.startsWith("enroll") || outcome === "nothing_pending") {
    return ["enroll", "Enrollment · nothing saved"];
  }
  if (outcome === "ok") return ["model", "Model + tools · checked in code"];
  if (outcome === "validation_failed") return ["warn", "Answer failed the checks · not shown"];
  return ["warn", "Model problem · nothing guessed"];
}

export default function ReplyTag({ metrics }) {
  if (!metrics) return null;
  const [kind, label] = tagFor(metrics);
  return <span className={`tag ${kind}`}>{label}</span>;
}
