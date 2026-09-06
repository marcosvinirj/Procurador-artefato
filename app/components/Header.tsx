'use client';

import Link from 'next/link';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useTranslation } from '@/lib/i18n';

export function Header() {
  const { t } = useTranslation();

  return (
    <header className="border-b border-edge/80 bg-ink/70 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 rounded-md">
          <span aria-hidden className="h-5 w-1.5 rounded-full bg-open" />
          <span className="font-mono text-sm font-semibold tracking-[0.18em] text-slate-100">
            TRENDPRINT
          </span>
        </Link>
        <div className="ml-auto flex items-center gap-3">
          <p className="hidden font-mono text-[11px] text-muted sm:block">{t('header.tagline')}</p>
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  );
}
