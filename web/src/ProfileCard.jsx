import { useEffect, useRef } from "react";

// The signed-in employee's own record. A course enrolled in during this session is highlighted once.
export default function ProfileCard({ profile }) {
  const seen = useRef({ id: null, enrolled: new Set() });
  const known = seen.current.id === profile?.id ? seen.current.enrolled : null;
  useEffect(() => {
    if (profile) seen.current = { id: profile.id, enrolled: new Set(profile.enrolled.map((c) => c.id)) };
  }, [profile]);

  if (!profile) return <div className="profile skeleton" aria-busy="true" />;
  const initials = profile.name.split(" ").map((part) => part[0]).join("");
  return (
    <div className="profile">
      <div className="profile-head">
        <span className="avatar">{initials}</span>
        <div>
          <h2>{profile.name}</h2>
          <p className="role">
            {profile.current_role} <span className="id-chip">{profile.id}</span>
          </p>
        </div>
      </div>
      <div className="interest">
        <span className="label">Career interest</span>
        <p>{profile.career_interest}</p>
      </div>
      <ProfileSection label="Skills">
        <div className="chips">
          {profile.skills.map((skill) => (
            <span className="chip skill" key={skill}>{skill}</span>
          ))}
        </div>
      </ProfileSection>
      <ProfileSection label="Completed">
        <CourseList courses={profile.completed} empty="none yet" />
      </ProfileSection>
      <ProfileSection label="Enrolled">
        <CourseList courses={profile.enrolled} empty="none yet" isNew={(id) => known && !known.has(id)} />
      </ProfileSection>
    </div>
  );
}

function ProfileSection({ label, children }) {
  return (
    <div className="profile-section">
      <span className="label">{label}</span>
      {children}
    </div>
  );
}

function CourseList({ courses, empty, isNew = () => false }) {
  if (!courses.length) return <p className="muted">{empty}</p>;
  return (
    <ul className="course-list">
      {courses.map((c) => (
        <li key={c.id} className={isNew(c.id) ? "new" : ""}>
          <span>{c.title}</span> <span className="id-chip">{c.id}</span>
        </li>
      ))}
    </ul>
  );
}
