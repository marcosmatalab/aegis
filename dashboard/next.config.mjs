/** @type {import('next').NextConfig} */

// Two build modes from one codebase.
//
//  - default: a SERVER build that reads AEGIS_REPORTS_DIR at REQUEST time, so a
//    fresh `aegis eval run` shows up on refresh. This is what `npm run dev` and
//    scripts/demo.sh use.
//  - AEGIS_STATIC_EXPORT=1: a fully STATIC export for GitHub Pages, where the
//    reports are read once at BUILD time from dashboard/sample-reports/ (real
//    output of a real run, committed) and baked into HTML.
//
// The dashboard only ever READS JSON — no backend, no state, no users — so the
// static export loses nothing except freshness, which the page states outright.
const isStaticExport = process.env.AEGIS_STATIC_EXPORT === "1";

const nextConfig = {
  // Offline by construction: no telemetry, no remote images, no external services.
  // (Next telemetry is also disabled in CI via `next telemetry disable`.)
  ...(isStaticExport
    ? {
        output: "export",
        // Pages serves a project site from /<repo>, so assets need the prefix.
        basePath: process.env.AEGIS_PAGES_BASE_PATH ?? "/aegis",
        images: { unoptimized: true },
        trailingSlash: true,
      }
    : {}),
};

export default nextConfig;
