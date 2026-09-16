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

  // 403 nao e falha: e um produto do plano pago aberto por quem esta no gratis.
  if (error.kind === 'http' && error.status === 403) {
    return (
      <div className="panel px-6 py-12 text-center">
        <p className="font-mono text-sm text-open">{t('locked.label')}</p>
        <p className="mx-auto mt-2 max-w-sm text-sm text-muted">{t('locked.detail')}</p>
      </div>
    );
  }

  const message =
    error.kind === 'network'
      ? t('error.network')
      : error.status === 401
        ? t('error.session')
        : t('error.http', { status: error.status ?? '—' });

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
