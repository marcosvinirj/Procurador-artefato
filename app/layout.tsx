import type { Metadata } from 'next';

import { Header } from '@/components/Header';
import { LanguageProvider } from '@/lib/i18n';

import './globals.css';

export const metadata: Metadata = {
  title: 'TrendPrint — what to print to sell',
  description:
    'Opportunity score for 3D prints: high buying demand while the market is still open.',
  // A app ja tem a sua propria traducao (ver LanguageProvider). Um tradutor de
  // browser por cima reescreve o texto sem saber do nosso re-render por score,
  // perde a referencia e mistura pedacos de idiomas diferentes no mesmo cartao.
  other: { google: 'notranslate' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" translate="no" className="notranslate">
      <body>
        <LanguageProvider>
          <Header />
          <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>
        </LanguageProvider>
      </body>
    </html>
  );
}
