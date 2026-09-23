'use client';

import { useState, type FormEvent } from 'react';

import { ErrorState } from '@/components/StateView';
import { deleteJson, postJson, useJson, type FetchError } from '@/lib/api';
import { categoryLabel, useTranslation } from '@/lib/i18n';

interface Shop {
  id: string;
  shop_name: string;
  category: string;
}

/** Lojas da Etsy vigiadas (core/shops.py). O vigia corre sozinho todos os dias;
 *  o botao corre-o ja. O que encontrar entra na lista de candidatos, como a
 *  descoberta do Google — nada fica publico sem aprovacao. */
export function WatchedShops({ onFound }: { onFound: () => void }) {
  const { t, locale } = useTranslation();
  const list = useJson<{ shops: Shop[]; categories: string[] }>('/api/admin/shops');
  const [shop, setShop] = useState('');
  const [category, setCategory] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ checked: number; added: number } | null>(null);

  const categories = list.data?.categories ?? [];
  const chosen = category || (categories.includes('geek') ? 'geek' : categories[0]) || '';

  async function run(id: string, action: () => Promise<void>, errorKey: (status?: number) => string) {
    setBusy(id);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(errorKey((cause as FetchError).status));
    } finally {
      setBusy(null);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    await run(
      'add',
      async () => {
        await postJson('/api/admin/shops', { shop: shop.trim(), category: chosen });
        setShop('');
        list.reload();
      },
      (status) =>
        status === 404
          ? 'admin.shops.error.not_found'
          : status === 422
            ? 'admin.shops.error.invalid'
            : 'admin.action_failed',
    );
  }

  async function watchNow() {
    setResult(null);
    await run(
      'watch',
      async () => {
        const found = await postJson<{ shops_checked: number; candidates_proposed: number }>('/api/admin/watch', {});
        setResult({ checked: found.shops_checked, added: found.candidates_proposed });
        onFound();
      },
      () => 'admin.action_failed',
    );
  }

  async function remove(id: string) {
    await run(
      id,
      async () => {
        await deleteJson(`/api/admin/shops/${id}`);
        list.reload();
      },
      () => 'admin.action_failed',
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">{t('admin.shops.title')}</h2>
          <p className="max-w-2xl text-sm text-muted">{t('admin.shops.hint')}</p>
        </div>
        <button
          type="button"
          disabled={busy === 'watch' || (list.data?.shops.length ?? 0) === 0}
          onClick={() => void watchNow()}
          className="btn-ghost px-4 py-2"
        >
          {busy === 'watch' ? t('admin.shops.watching') : t('admin.shops.watch')}
        </button>
      </div>

      {result && (
        <p role="status" className="font-mono text-[11px] text-open">
          {t('admin.shops.watched', { checked: result.checked, added: result.added })}
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-lg border border-tight/40 bg-tight/10 px-4 py-3 text-sm text-tight">
          {t(error)}
        </p>
      )}

      <form onSubmit={add} className="panel flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
        <label className="block flex-1 space-y-1.5">
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">{t('admin.shops.input')}</span>
          <input
            required
            maxLength={200}
            value={shop}
            onChange={(event) => setShop(event.target.value)}
            placeholder="etsy.com/shop/…"
            className="w-full rounded-lg border border-edge bg-ink/70 px-3 py-2.5 text-base text-slate-100"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">
            {t('admin.shops.category')}
          </span>
          <select
            value={chosen}
            onChange={(event) => setCategory(event.target.value)}
            className="w-full rounded-lg border border-edge bg-ink/70 px-3 py-2.5 text-base text-slate-100 sm:w-44"
          >
            {categories.map((value) => (
              <option key={value} value={value}>
                {categoryLabel(locale, value)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy === 'add' || !chosen} className="btn-primary px-4 py-2.5">
          {busy === 'add' ? t('admin.shops.adding') : t('admin.shops.add')}
        </button>
      </form>

      {list.error && <ErrorState error={list.error} onRetry={list.reload} />}
      {list.data && list.data.shops.length === 0 && (
        <p className="panel px-4 py-6 text-sm text-muted">{t('admin.shops.empty')}</p>
      )}
      {list.data && list.data.shops.length > 0 && (
        <ul className="panel divide-y divide-edge/60">
          {list.data.shops.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="flex min-w-0 items-center gap-2">
                <a
                  href={`https://www.etsy.com/shop/${encodeURIComponent(item.shop_name)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="truncate text-slate-100 hover:text-open"
                >
                  {item.shop_name} ↗
                </a>
                <span className="chip shrink-0">{categoryLabel(locale, item.category)}</span>
              </div>
              <button
                type="button"
                disabled={busy === item.id}
                onClick={() => void remove(item.id)}
                className="shrink-0 text-xs text-muted transition hover:text-tight disabled:opacity-50"
              >
                {t('admin.shops.remove')}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
