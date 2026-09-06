import type { Metadata } from 'next';

import { Header } from '@/components/Header';
import { LanguageProvider } from '@/lib/i18n';

import './globals.css';

export const metadata: Metadata = {
  title: 'TrendPrint — what to print to sell',
  description:
    'Opportunity score for 3D prints: high buying demand while the market is still open.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <LanguageProvider>
          <Header />
          <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>
        </LanguageProvider>
      </body>
    </html>
  );
}
