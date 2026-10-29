// The validated recommendation as cards. Titles come from the data (F12); only the short reason is model text.
const GROUPS = [
  { key: "skills", label: "Skills to develop", id: "skill_id", name: "name", tone: "skill" },
  { key: "courses", label: "Courses", id: "course_id", name: "title", tone: "course" },
  { key: "roles", label: "Roles to explore", id: "job_id", name: "title", tone: "role" },
];

export default function RecommendationCards({ recommendation }) {
  if (!recommendation) return null;
  let order = 0; // staggers the cards' entrance
  return (
    <div className="cards">
      <p className="cards-intro">Here is what I suggest for your next career step.</p>
      {GROUPS.map((g) => (
        <section key={g.key} className={`group ${g.tone}`}>
          <h3>
            {g.label} <span className="count">{recommendation[g.key].length}</span>
          </h3>
          <div className="group-cards">
            {recommendation[g.key].map((item, i) => (
              <article className="card" key={item[g.id]} style={{ animationDelay: `${order++ * 60}ms` }}>
                <div className="card-title">
                  <span className="card-number">{i + 1}</span>
                  <strong>{item[g.name]}</strong>
                  <span className="id-chip">{item[g.id]}</span>
                </div>
                <p>{item.reason}</p>
                <div className="sources">
                  <span>from</span>
                  {item.sources.map((source) => (
                    <span className="source" key={source}>{source}</span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
      <p className="cards-hint">To sign up, ask for example: "Enroll me in the first course".</p>
    </div>
  );
}
