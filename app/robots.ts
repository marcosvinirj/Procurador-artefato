import type { MetadataRoute } from 'next';

import { SITE_URL } from '@/lib/site';

/** O Google so ve as paginas publicas; admin e API ficam de fora. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/', disallow: ['/admin', '/api/', '/login/reset'] },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
