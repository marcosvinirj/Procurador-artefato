/** @type {import('next').NextConfig} */
const nextConfig = {
  // Em dev o FastAPI corre a parte (uvicorn :8000); em producao a Vercel encaminha
  // /api/* para a funcao Python. Nos dois casos o browser fala sempre same-origin,
  // por isso nao ha CORS aberto nem chaves expostas no cliente.
  async rewrites() {
    if (process.env.NODE_ENV !== 'development') return [];
    return [{ source: '/api/:path*', destination: 'http://127.0.0.1:8000/api/:path*' }];
  },
};

export default nextConfig;
