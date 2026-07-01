import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  async rewrites() {
    const internal = process.env.API_INTERNAL_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: internal + '/api/:path*',
      },
    ];
  },
};

export default nextConfig;
