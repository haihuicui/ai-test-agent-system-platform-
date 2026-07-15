/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // API_INTERNAL_URL：服务端 rewrite 目标（容器部署时指向内网服务，如 http://backend:8001）。
    // 浏览器侧的 NEXT_PUBLIC_API_URL 可留空走同源相对路径，两者解耦；本地开发不设 API_INTERNAL_URL 时行为不变。
    const apiUrl =
      process.env.API_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8001";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

