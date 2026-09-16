'use client';

import Link from 'next/link';
import { Fragment } from 'react';

import { OpportunityScale } from '@/components/OpportunityScale';
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
    <section className="mx-auto flex max-w-2xl flex-col items-center gap-8 py-6 text-center sm:py-14">
      <OpportunityScale large />
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-50 sm:text-5xl">
          {t('page.heading')}
        </h1>
        <p className="mx-auto max-w-lg text-base leading-relaxed text-muted">{t('welcome.body')}</p>
      </div>
      {available ? (
        <div className="flex flex-wrap justify-center gap-3">
          <Link href="/signup" className="btn-primary">
            {t('welcome.signup')}
          </Link>
          <Link href="/login" className="btn-ghost">
            {t('header.sign_in')}
          </Link>
        </div>
      ) : (
        <p className="text-sm text-muted">{t('login.unavailable')}</p>
      )}
    </section>
  );
}
