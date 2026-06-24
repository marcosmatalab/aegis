/**
 * Explicit "this report/datum is absent" panel. Used whenever a report is missing or
 * unparseable — so a gap reads as an honest "Not available" (with the command to
 * produce it), NEVER as a zero, a blank, or an empty chart that looks fine.
 */
export function AbsentPanel({
  title,
  reason,
  hint,
}: {
  title: string;
  reason: string;
  hint?: string;
}) {
  return (
    <section
      data-absent="true"
      style={{
        border: "1px dashed #39404a",
        borderRadius: 8,
        padding: "1rem",
        color: "#9aa0aa",
        background: "#14171d",
      }}
    >
      <h3 style={{ margin: "0 0 0.25rem" }}>{title}</h3>
      <p style={{ margin: 0 }}>
        <strong>Not available</strong> — {reason}
      </p>
      {hint ? (
        <p style={{ margin: "0.35rem 0 0", fontSize: 13, opacity: 0.85 }}>Hint: {hint}</p>
      ) : null}
    </section>
  );
}
