/** @type {import('next').NextConfig} */
const nextConfig = {
  // Offline by construction: no telemetry, no remote images, no external services.
  // (Next telemetry is also disabled in CI via `next telemetry disable`.)
};

export default nextConfig;
