// What the assistant is doing while you wait. Steps come from the stream's status lines: one per tool the
// model chose, in order. The last one is still running; the ones before it are done.
const LABELS = {
  get_employee_profile: "Reading your profile",
  search_courses: "Searching the course catalog",
  search_jobs: "Searching internal roles",
  enroll_in_course: "Finding the course you mean",
  saving: "Saving your answer",
};

export default function WorkingSteps({ steps }) {
  if (!steps.length) {
    return (
      <div className="bubble working">
        <span className="dots" aria-label="working"><i /><i /><i /></span>
      </div>
    );
  }
  return (
    <div className="bubble working">
      <ol className="steps">
        {steps.map((step, i) => {
          const active = i === steps.length - 1;
          return (
            <li key={step} className={active ? "active" : "done"}>
              <span className="mark" aria-hidden="true">{active ? "" : "✓"}</span>
              {LABELS[step] || step}
              {active && <span className="dots"><i /><i /><i /></span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
