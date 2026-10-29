// The validated recommendation as cards. Titles come from the data (F12); only the short reason is model text.
const GROUPS = [
  { key: "skills", label: "Skills to develop", id: "skill_id", name: "name" },
  { key: "courses", label: "Courses", id: "course_id", name: "title" },
  { key: "roles", label: "Roles to explore", id: "job_id", name: "title" },
];

export default function RecommendationCards({ recommendation }) {
  if (!recommendation) return null;
  return (
    <div className="cards">
      {GROUPS.map((g) => (
        <section key={g.key}>
          <h3>{g.label}</h3>
          {recommendation[g.key].map((item) => (
            <div className="card" key={item[g.id]}>
              <strong>
                {item[g.name]} <small>[{item[g.id]}]</small>
              </strong>
              <p>{item.reason}</p>
              <small>from {item.sources.join(", ")}</small>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
