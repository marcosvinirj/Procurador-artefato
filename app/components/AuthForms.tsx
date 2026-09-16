'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useId, useState, type FormEvent } from 'react';

import { OpportunityScale } from '@/components/OpportunityScale';
import { useAuth, type AuthResult } from '@/lib/auth';
import { useTranslation } from '@/lib/i18n';

type Mode = 'signin' | 'signup' | 'forgot';

/** Codigos do Supabase com mensagem propria; o resto cai no generico. */
const ERROR_KEY: Record<string, string> = {
  invalid_credentials: 'login.error.invalid_credentials',
  email_not_confirmed: 'login.error.email_not_confirmed',
  weak_password: 'login.error.weak_password',
  same_password: 'login.error.same_password',
  over_email_send_rate_limit: 'login.error.rate_limit',
  over_request_rate_limit: 'login.error.rate_limit',
  unavailable: 'login.unavailable',
};

/** Estado comum aos formularios: um pedido de cada vez, erro como codigo. */
function useSubmit() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(action: () => Promise<AuthResult>): Promise<boolean> {
    setBusy(true);
    setError(null);
    const result = await action();
    setBusy(false);
    if (!result.ok) setError(result.code);
    return result.ok;
  }
  return { busy, error, setError, submit };
}

export function LoginForm({ initial }: { initial: Mode }) {
  const { t } = useTranslation();
  const router = useRouter();
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>(initial);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const { busy, error, setError, submit } = useSubmit();

  // Com sessao (acabou de entrar, ou voltou do link de confirmacao): catalogo.
  useEffect(() => {
    if (auth.session) router.replace('/');
  }, [auth.session, router]);

  function switchTo(next: Mode) {
    setMode(next);
    setError(null);
    setNotice(null);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const address = email.trim();
    if (mode === 'signin') await submit(() => auth.signIn(address, password));
    else if (mode === 'signup' && (await submit(() => auth.signUp(address, password)))) setNotice('login.done.signup');
    else if (mode === 'forgot' && (await submit(() => auth.requestReset(address)))) setNotice('login.done.forgot');
  }

  async function resend() {
    if (await submit(() => auth.resendConfirmation(email.trim()))) setNotice('login.done.signup');
  }

  if (!auth.available) {
    return (
      <AuthShell title={t('login.title.signin')}>
        <p className="text-sm text-muted">{t('login.unavailable')}</p>
      </AuthShell>
    );
  }

  // Quem esta a entrar pode ir criar conta; quem cria ou recupera, volta a entrar.
  const footer = (
    <p>
      {t(`login.prompt.${mode}`)}{' '}
      <TextButton onClick={() => switchTo(mode === 'signin' ? 'signup' : 'signin')} strong>
        {t(mode === 'signin' ? 'login.link.signup' : 'login.link.signin')}
      </TextButton>
    </p>
  );

  return (
    <AuthShell title={t(`login.title.${mode}`)} subtitle={notice ? undefined : t(`login.subtitle.${mode}`)} footer={footer}>
      {notice ? (
        <p role="status" className="border-l-2 border-open pl-4 text-sm leading-relaxed text-slate-200">
          {t(notice, { email: email.trim() })}
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-5">
          <Field
            label={t('login.email_label')}
            type="email"
            autoComplete="email"
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          {mode !== 'forgot' && (
            <Field
              label={t('login.password_label')}
              hint={mode === 'signup' ? t('login.password_hint') : undefined}
              action={
                mode === 'signin' && (
                  <TextButton onClick={() => switchTo('forgot')}>{t('login.to_forgot')}</TextButton>
                )
              }
              type="password"
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
              minLength={mode === 'signup' ? 8 : undefined}
              maxLength={72}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
          <AuthError code={error} />
          {error === 'email_not_confirmed' && (
            <TextButton onClick={() => void resend()} disabled={busy} strong>
              {t('login.resend')}
            </TextButton>
          )}
          <SubmitButton busy={busy}>{t(`login.submit.${mode}`)}</SubmitButton>
        </form>
      )}
    </AuthShell>
  );
}

/** Destino do link "esqueci a senha". O link abre uma sessao de recuperacao
 *  (PKCE: so no navegador que o pediu); sem ela nao ha senha para mudar. */
export function ResetPasswordForm() {
  const { t } = useTranslation();
  const router = useRouter();
  const { ready, session, updatePassword } = useAuth();
  const [password, setPassword] = useState('');
  const { busy, error, submit } = useSubmit();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (await submit(() => updatePassword(password))) router.replace('/');
  }

  return (
    <AuthShell title={t('login.title.reset')}>
      {!ready && <p className="text-sm text-muted">{t('login.busy')}</p>}
      {ready && !session && (
        <div className="space-y-5">
          <p className="text-sm leading-relaxed text-muted">{t('login.reset_invalid')}</p>
          <Link href="/login" className="btn-ghost">
            {t('login.submit.signin')}
          </Link>
        </div>
      )}
      {ready && session && (
        <form onSubmit={onSubmit} className="space-y-5">
          <Field
            label={t('login.new_password_label')}
            hint={t('login.password_hint')}
            type="password"
            autoComplete="new-password"
            minLength={8}
            maxLength={72}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <AuthError code={error} />
          <SubmitButton busy={busy}>{t('login.submit.reset')}</SubmitButton>
        </form>
      )}
    </AuthShell>
  );
}

/** Formulario a esquerda; a direita, o medidor que a pessoa vai usar la dentro. */
function AuthShell({
  title,
  subtitle,
  footer,
  children,
}: {
  title: string;
  subtitle?: string;
  footer?: React.ReactNode;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="mx-auto grid max-w-4xl gap-4 py-2 sm:py-8 lg:grid-cols-2 lg:gap-0">
      <section className="panel flex flex-col p-6 sm:p-10 lg:rounded-r-none">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-2 text-sm leading-relaxed text-muted">{subtitle}</p>}
        <div className="mt-8 flex-1">{children}</div>
        {footer && <div className="mt-8 border-t border-edge pt-5 text-sm text-muted">{footer}</div>}
      </section>
      <aside className="flex flex-col items-center justify-center gap-6 rounded-xl border border-edge bg-ink/60 p-6 sm:p-10 lg:rounded-l-none lg:border-l-0">
        <OpportunityScale />
        <p className="max-w-xs text-center text-xs leading-relaxed text-muted">{t('scale.caption')}</p>
      </aside>
    </div>
  );
}

function Field({
  label,
  hint,
  action,
  type,
  ...input
}: {
  label: string;
  hint?: string;
  action?: React.ReactNode;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  const { t } = useTranslation();
  const id = useId();
  const [revealed, setRevealed] = useState(false);
  const secret = type === 'password';

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="font-mono text-[11px] uppercase tracking-wider text-muted">
          {label}
        </label>
        {action}
      </div>
      <div className="relative mt-2">
        {/* 16px: abaixo disso o Safari do iPad/iPhone faz zoom ao tocar no campo. */}
        <input
          id={id}
          required
          type={secret && revealed ? 'text' : type}
          {...input}
          className={`w-full rounded-lg border border-edge bg-ink/70 px-4 py-3 text-base text-slate-100 transition focus:border-open/60 ${secret ? 'pr-24' : ''}`}
        />
        {secret && (
          <button
            type="button"
            onClick={() => setRevealed((value) => !value)}
            aria-pressed={revealed}
            className="absolute inset-y-1 right-1 rounded-md px-3 font-mono text-[11px] uppercase tracking-wider text-muted transition hover:text-open"
          >
            {t(revealed ? 'login.hide' : 'login.show')}
          </button>
        )}
      </div>
      {hint && <p className="mt-2 text-xs text-muted">{hint}</p>}
    </div>
  );
}

function AuthError({ code }: { code: string | null }) {
  const { t } = useTranslation();
  if (!code) return null;
  return (
    <p role="alert" className="rounded-lg border border-tight/40 bg-tight/10 px-4 py-3 text-sm text-tight">
      {t(ERROR_KEY[code] ?? 'login.error.generic')}
    </p>
  );
}

function SubmitButton({ busy, children }: { busy: boolean; children: React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <button type="submit" disabled={busy} className="btn-primary w-full">
      {busy ? t('login.busy') : children}
    </button>
  );
}

function TextButton({ strong = false, ...props }: { strong?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`rounded text-sm transition disabled:opacity-50 ${
        strong ? 'font-medium text-open hover:underline' : 'text-muted hover:text-open'
      }`}
    />
  );
}
