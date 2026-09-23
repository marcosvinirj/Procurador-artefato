'use client';

import { useState } from 'react';

import { RequireLogin } from '@/components/RequireLogin';
import { ErrorState, LoadingGrid } from '@/components/StateView';
import { WatchedShops } from '@/components/WatchedShops';
import { postJson, useJson } from '@/lib/api';
import { categoryLabel, useTranslation } from '@/lib/i18n';
import { formatNumber } from '@/lib/score';

interface AdminUser {
  id: string;
  email: string | null;
  is_paid: boolean;
  is_admin: boolean;
  created_at: string | null;
}

interface Overview {
  users: AdminUser[];
  models: Record<string, number>;
}

interface Candidate {
  id: string;
  name: string;
  category: string;
  keyword: string;
  source: string | null;
  demand_raw: number | null;
  competition_raw: number | null;
  margin_est: number | null;
}

// Espelha core/shops.SOURCE: o vigia grava a loja de origem como "etsy_shop:<nome>".
const SHOP_SOURCE = 'etsy_shop:';

export function AdminPanel() {
  return (
    <RequireLogin>
      <Admin />
    </RequireLogin>
  );
}

/** A pagina so mostra o que a API deixar: sem is_admin, /api/admin responde 403. */
function Admin() {
  const { t, locale } = useTranslation();
  const overview = useJson<Overview>('/api/admin');
  const candidates = useJson<{ candidates: Candidate[] }>('/api/candidates');
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [found, setFound] = useState<{ added: number; rejected: number } | null>(null);

  async function searchNow() {
    setFound(null);
    await act('search', async () => {
      const result = await postJson<{ candidates_proposed: number; duplicates_rejected: number }>(
        '/api/admin/discover',
        {},
      );
      setFound({ added: result.candidates_proposed, rejected: result.duplicates_rejected });
    }, () => {
      candidates.reload();
      overview.reload();
    });
  }

  async function act(id: string, request: () => Promise<unknown>, reload: () => void) {
    setBusy(id);
    setFailed(false);
    try {
      await request();
      reload();
    } catch {
      setFailed(true);
    } finally {
      setBusy(null);
    }
  }

  if (overview.error?.kind === 'http' && overview.error.status === 403) {
    return (
      <div className="panel px-6 py-12 text-center">
        <p className="text-sm text-muted">{t('admin.denied')}</p>
      </div>
    );
  }
  // Mantem os dados no ecra enquanto recarrega depois de uma acao (sem piscar).
  if (!overview.data) {
    return overview.error ? <ErrorState error={overview.error} onRetry={overview.reload} /> : <LoadingGrid />;
  }

  const { users, models } = overview.data;
  const stats: [string, number][] = [
    ['admin.stat.users', users.length],
    ['admin.stat.paid', users.filter((user) => user.is_paid).length],
    ['admin.stat.active', models.active ?? 0],
    ['admin.stat.pending', models.pending ?? 0],
    ['admin.stat.archived', models.archived ?? 0],
  ];
  const pending = candidates.data?.candidates ?? [];

  return (
    <div className="space-y-10">
      <section className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">{t('admin.title')}</h1>
        <p className="text-sm text-muted">{t('admin.subtitle')}</p>
      </section>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {stats.map(([key, value]) => (
          <div key={key} className="panel p-4">
            <dt className="font-mono text-[11px] uppercase tracking-wider text-muted">{t(key)}</dt>
            <dd className="mt-1 text-2xl font-semibold text-slate-50">{value}</dd>
          </div>
        ))}
      </dl>

      {failed && (
        <p role="alert" className="rounded-lg border border-tight/40 bg-tight/10 px-4 py-3 text-sm text-tight">
          {t('admin.action_failed')}
        </p>
      )}

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-50">{t('admin.users.title')}</h2>
          <p className="text-sm text-muted">{t('admin.users.hint')}</p>
        </div>
        {users.length === 0 ? (
          <p className="panel px-4 py-6 text-sm text-muted">{t('admin.users.empty')}</p>
        ) : (
          <div className="panel overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-edge text-left font-mono text-[11px] uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-4 py-3 font-normal">{t('admin.users.email')}</th>
                  <th className="px-4 py-3 font-normal">{t('admin.users.created')}</th>
                  <th className="px-4 py-3 text-right font-normal">{t('admin.users.plan')}</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b border-edge/60 last:border-0">
                    <td className="px-4 py-3 text-slate-100">
                      {user.email ?? '—'}
                      {user.is_admin && <span className="chip ml-2 border-open/50 text-open">admin</span>}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-muted">
                      {user.created_at?.slice(0, 10) ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        disabled={busy === user.id}
                        aria-pressed={user.is_paid}
                        onClick={() =>
                          void act(
                            user.id,
                            () => postJson(`/api/admin/users/${user.id}`, { is_paid: !user.is_paid }),
                            overview.reload,
                          )
                        }
                        className={`chip transition disabled:opacity-50 ${
                          user.is_paid ? 'border-open/60 bg-open/10 text-open' : 'hover:border-open hover:text-open'
                        }`}
                      >
                        {t(user.is_paid ? 'admin.plan.paid' : 'admin.plan.free')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <WatchedShops onFound={candidates.reload} />

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-50">{t('admin.candidates.title')}</h2>
            <p className="text-sm text-muted">{t('admin.candidates.hint')}</p>
          </div>
          <button
            type="button"
            disabled={busy === 'search'}
            onClick={() => void searchNow()}
            className="btn-ghost px-4 py-2"
          >
            {busy === 'search' ? t('admin.candidates.searching') : t('admin.candidates.search')}
          </button>
        </div>
        {found && (
          <p role="status" className="font-mono text-[11px] text-open">
            {t('admin.candidates.found', { added: found.added, rejected: found.rejected })}
          </p>
        )}
        {candidates.error && <ErrorState error={candidates.error} onRetry={candidates.reload} />}
        {!candidates.error && pending.length === 0 && (
          <p className="panel px-4 py-6 text-sm text-muted">
            {candidates.data ? t('admin.candidates.empty') : t('state.loading')}
          </p>
        )}
        <ul className="grid gap-3 sm:grid-cols-2">
          {pending.map((candidate) => (
            <li key={candidate.id} className="panel flex flex-col gap-3 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium text-slate-100">{candidate.name}</p>
                  <p className="font-mono text-xs text-muted">{candidate.keyword}</p>
                  <p className="mt-1 font-mono text-[11px] text-open/80">
                    {candidate.source?.startsWith(SHOP_SOURCE)
                      ? t('admin.candidates.from_shop', { shop: candidate.source.slice(SHOP_SOURCE.length) })
                      : t('admin.candidates.from_google')}
                  </p>
                </div>
                <span className="chip shrink-0">{categoryLabel(locale, candidate.category)}</span>
              </div>
              <dl className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                {(
                  [
                    ['metric.demand', candidate.demand_raw],
                    ['stat.competition_full', candidate.competition_raw],
                    ['admin.candidates.price', candidate.margin_est],
                  ] as const
                ).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-muted">{t(key)}</dt>
                    <dd className="mt-0.5 text-slate-200">{formatNumber(value)}</dd>
                  </div>
                ))}
              </dl>
              <div className="flex gap-2">
                {(['approve', 'reject'] as const).map((action) => (
                  <button
                    key={action}
                    type="button"
                    disabled={busy === candidate.id}
                    onClick={() =>
                      void act(
                        candidate.id,
                        () => postJson(`/api/candidates/${candidate.id}`, { action }),
                        () => {
                          candidates.reload();
                          overview.reload();
                        },
                      )
                    }
                    className={`${action === 'approve' ? 'btn-primary' : 'btn-ghost'} flex-1 px-3 py-2`}
                  >
                    {t(`admin.candidates.${action}`)}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
