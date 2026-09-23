import type { MetadataRoute } from 'next';

import { SITE_URL } from '@/lib/site';

/** So as paginas que qualquer pessoa abre sem conta. */
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${SITE_URL}/`, changeFrequency: 'daily', priority: 1 },
    { url: `${SITE_URL}/how-it-works`, changeFrequency: 'monthly', priority: 0.9 },
    { url: `${SITE_URL}/signup`, changeFrequency: 'yearly', priority: 0.6 },
  ];
}
