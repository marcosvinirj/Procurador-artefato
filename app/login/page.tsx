'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';

import { useAuth } from '@/lib/auth';
import { useTranslation } from '@/lib/i18n';

type Phase = 'idle' | 'sending' | 'sent' | 'error';

export default function LoginPage() {
  const { t } = useTranslation();
  const { available, session, signIn, signOut } = useAuth();
  const [email, setEmail] = useState('');
  const [phase, setPhase] = useState<Phase>('idle');

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPhase('sending');
    setPhase((await signIn(email.trim())) ? 'sent' : 'error');
  }

  return (
    <div className="mx-auto max-w-sm space-y-6 py-6">
      <Link
        href="/"
        className="inline-flex rounded font-mono text-xs uppercase tracking-wider text-muted transition hover:text-open"
      >
        {t('login.back')}
      </Link>

      <section className="panel space-y-4 p-6">
        <h1 className="text-xl font-semibold tracking-tight text-slate-50">{t('login.title')}</h1>

        {!available && <p className="text-sm text-muted">{t('login.unavailable')}</p>}

        {available && session && (
          <div className="space-y-4">
            <p className="text-sm text-slate-200">
              {t('login.signed_in_as', { email: session.user.email ?? '' })}
            </p>
            <button
              type="button"
              onClick={() => void signOut()}
              className="rounded-md border border-edge px-4 py-2 font-mono text-xs uppercase tracking-wider text-slate-200 transition hover:border-tight hover:text-tight"
            >
              {t('header.sign_out')}
            </button>
          </div>
        )}

        {available && !session && phase === 'sent' && (
          <div role="status" className="space-y-2">
            <p className="font-mono text-sm text-open">{t('login.sent_title')}</p>
            <p className="text-sm text-muted">{t('login.sent_body', { email })}</p>
          </div>
        )}

        {available && !session && phase !== 'sent' && (
          <form onSubmit={onSubmit} className="space-y-4">
            <p className="text-sm text-muted">{t('login.subtitle')}</p>
            <label className="block space-y-1.5">
              <span className="font-mono text-[11px] uppercase tracking-wider text-muted">
                {t('login.email_label')}
              </span>
              <input
                type="email"
                required
                autoComplete="email"
                maxLength={254}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-lg border border-edge bg-panel/80 px-3 py-2.5 font-mono text-sm text-slate-100"
              />
            </label>
            {phase === 'error' && (
              <p role="alert" className="text-sm text-tight">
                {t('login.error')}
              </p>
            )}
            <button
              type="submit"
              disabled={phase === 'sending'}
              className="w-full rounded-md border border-open bg-open/10 px-4 py-2.5 font-mono text-xs uppercase tracking-wider text-open transition hover:bg-open/20 disabled:opacity-50"
            >
              {phase === 'sending' ? t('login.sending') : t('login.submit')}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
