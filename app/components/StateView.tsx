'use client';

import type { FetchError } from '@/lib/api';
import { useTranslation } from '@/lib/i18n';

export function LoadingGrid() {
  const { t } = useTranslation();
  return (
    <div
      role="status"
      aria-live="polite"
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
    >
      <span className="sr-only">{t('state.loading')}</span>
      {Array.from({ length: 6 }, (_, index) => (
        <div key={index} className="panel h-[168px] animate-pulse" aria-hidden />
      ))}
    </div>
  );
}

export function EmptyState({ messageKey }: { messageKey: string }) {
  const { t } = useTranslation();
  return (
    <div className="panel px-6 py-14 text-center">
      <p className="font-mono text-sm text-slate-200">{t('state.empty_title')}</p>
      <p className="mx-auto mt-2 max-w-sm text-sm text-muted">{t(messageKey)}</p>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: FetchError; onRetry: () => void }) {
  const { t } = useTranslation();
  const message =
    error.kind === 'http' ? t('error.http', { status: error.status ?? '—' }) : t('error.network');

  return (
    <div role="alert" className="panel border-tight/40 px-6 py-12 text-center">
      <p className="font-mono text-sm text-tight">{t('state.error_title')}</p>
      <p className="mx-auto mt-2 max-w-sm text-sm text-muted">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-5 rounded-md border border-edge px-4 py-2 font-mono text-xs uppercase tracking-wider text-slate-200 transition hover:border-open hover:text-open"
      >
        {t('state.retry')}
      </button>
    </div>
  );
}
