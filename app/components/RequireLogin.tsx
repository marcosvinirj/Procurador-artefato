'use client';

import Link from 'next/link';
import { Fragment } from 'react';

import { LoadingGrid } from '@/components/StateView';
import { useAuth } from '@/lib/auth';
import { useTranslation } from '@/lib/i18n';

/** O catalogo so abre com sessao. O bloqueio real e na API (401 sem login);
 *  aqui so se escolhe o que mostrar. */
export function RequireLogin({ children }: { children: React.ReactNode }) {
  const { ready, session } = useAuth();
  if (!ready) return <LoadingGrid />;
  if (!session) return <Welcome />;
  // Trocar de conta remonta o conteudo: os dados voltam a ser pedidos com o token novo.
  return <Fragment key={session.user.id}>{children}</Fragment>;
}

function Welcome() {
  const { t } = useTranslation();
  const { available } = useAuth();
  return (
    <section className="mx-auto max-w-xl space-y-5 py-12 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">
        {t('page.heading')}
      </h1>
      <p className="text-sm leading-relaxed text-muted">{t('welcome.body')}</p>
      {available ? (
        <div className="flex flex-wrap justify-center gap-3">
          <Link
            href="/signup"
            className="rounded-md border border-open bg-open/10 px-4 py-2.5 font-mono text-xs uppercase tracking-wider text-open transition hover:bg-open/20"
          >
            {t('welcome.signup')}
          </Link>
          <Link
            href="/login"
            className="rounded-md border border-edge px-4 py-2.5 font-mono text-xs uppercase tracking-wider text-slate-200 transition hover:border-open hover:text-open"
          >
            {t('header.sign_in')}
          </Link>
        </div>
      ) : (
        <p className="text-sm text-muted">{t('login.unavailable')}</p>
      )}
    </section>
  );
}
