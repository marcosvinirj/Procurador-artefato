import type { Metadata } from 'next';
import Link from 'next/link';

import './globals.css';

export const metadata: Metadata = {
  title: 'TrendPrint — o que imprimir para vender',
  description:
    'Score de oportunidade para prints 3D: procura de compra alta com o mercado ainda por fechar.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt">
      <body>
        <header className="border-b border-edge/80 bg-ink/70 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5 rounded-md">
              <span aria-hidden className="h-5 w-1.5 rounded-full bg-open" />
              <span className="font-mono text-sm font-semibold tracking-[0.18em] text-slate-100">
                TRENDPRINT
              </span>
            </Link>
            <p className="ml-auto hidden font-mono text-[11px] text-muted sm:block">
              procura alta · concorrencia baixa
            </p>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>
      </body>
    </html>
  );
}
