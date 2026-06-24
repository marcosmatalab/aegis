import type { ReactNode } from "react";

/** A titled panel container. `caveat` (when given) renders as a persistent, visible
 * note under the title — caveats are never hidden behind a tooltip. */
export function Card({
  title,
  subtitle,
  caveat,
  children,
}: {
  title: string;
  subtitle?: string;
  caveat?: string;
  children: ReactNode;
}) {
  return (
    <section
      style={{
        border: "1px solid #2c313a",
        borderRadius: 8,
        padding: "1rem 1.25rem",
        background: "#14171d",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>
        {subtitle ? <span style={{ color: "#9aa0aa", fontSize: 13 }}>{subtitle}</span> : null}
      </div>
      {caveat ? (
        <p style={{ margin: "0.4rem 0 0", color: "#e0b15e", fontSize: 12.5 }}>⚠ {caveat}</p>
      ) : null}
      <div style={{ marginTop: "0.75rem" }}>{children}</div>
    </section>
  );
}
