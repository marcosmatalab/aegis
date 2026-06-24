import type { ReactNode } from "react";

import { LocaleProvider } from "@/lib/i18n/LocaleProvider";

// metadata/<title> stays English by design (out of scope for the i18n toggle).
export const metadata = {
  title: "Aegis Dashboard",
  description: "Read-only view of Aegis's real eval / red-team / calibration / evidence reports.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif",
          background: "#0b0e14",
          color: "#e6e6e6",
        }}
      >
        <LocaleProvider>{children}</LocaleProvider>
      </body>
    </html>
  );
}
