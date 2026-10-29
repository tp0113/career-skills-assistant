export default function EnrollConfirm({ pending, disabled, onAnswer }) {
  return (
    <div className="confirm">
      <button disabled={disabled} onClick={() => onAnswer(true, pending.course_id)}>
        Confirm
      </button>
      <button className="secondary" disabled={disabled} onClick={() => onAnswer(false, pending.course_id)}>
        Decline
      </button>
    </div>
  );
}
