/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    proxyTimeout: 300000, // 5 minutes
  },
  async rewrites() {
    return [
      {
        source: '/api/proxy/:path*',
        destination: `${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/:path*`, // Proxy to Backend (Env Var or Localhost)
      },
    ];
  },
};

export default nextConfig;
