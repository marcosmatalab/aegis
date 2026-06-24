import { statusTone, type Tone } from "@/lib/status";

const TONE_STYLE: Record<Tone, { bg: string; fg: string; border: string }> = {
  success: { bg: "#0f2e1a", fg: "#5ee08a", border: "#1f5c39" },
  warn: { bg: "#33260a", fg: "#e0b15e", border: "#5c4a1f" },
  muted: { bg: "#22262e", fg: "#9aa0aa", border: "#39404a" },
  neutral: { bg: "#1a1d24", fg: "#7a808a", border: "#2c313a" },
};

/**
 * Render a status pill. The label is the VERBATIM status string (never relabeled or
 * recolored toward success); `statusTone` decides the colour, and only measured/
 * covered get the success treatment.
 */
export function StatusBadge({ status }: { status: string }) {
  const tone = statusTone(status);
  const s = TONE_STYLE[tone];
  return (
    <span
      data-tone={tone}
      title={status}
      style={{
        display: "inline-block",
        padding: "1px 8px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        background: s.bg,
        color: s.fg,
        border: `1px solid ${s.border}`,
      }}
    >
      {status}
    </span>
  );
}
