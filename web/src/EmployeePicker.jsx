export default function EmployeePicker({ employees, value, onChange, disabled }) {
  return (
    <label className="picker">
      Signed in as
      <select value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
        {employees.map((e) => (
          <option key={e.id} value={e.id}>
            {e.name} ({e.id})
          </option>
        ))}
      </select>
    </label>
  );
}
