/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emits a self-contained server bundle for the Docker runner stage.
  output: "standalone",
  // Proxy /api to the Python backend so the browser sees one origin.
  // In production set BACKEND_URL to the deployed FastAPI service.
  async rewrites() {
    const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};
export default nextConfig;
