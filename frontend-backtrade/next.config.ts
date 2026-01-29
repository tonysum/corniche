import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: 'standalone',
  
  // 允许开发模式下的跨域请求（用于从外部 IP 访问）
  // 生产环境建议使用反向代理（如 Nginx）
  ...(process.env.NODE_ENV === 'development' && {
    allowedDevOrigins: [
      '8.216.33.6',  // 服务器 IP
      '192.168.2.103',  // 本地网络 IP
      'localhost',
      '127.0.0.1',
      // 如果需要允许所有 IP（不推荐，仅用于测试）
      // '*'
    ],
  }),
};

export default nextConfig;
