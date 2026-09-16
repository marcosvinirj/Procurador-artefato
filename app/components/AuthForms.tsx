'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';

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
      <AuthCard title={t('login.title.signin')}>
        <p className="text-sm text-muted">{t('login.unavailable')}</p>
      </AuthCard>
    );
  }

  return (
    <AuthCard title={t(`login.title.${mode}`)}>
      {notice ? (
        <p role="status" className="text-sm leading-relaxed text-slate-200">
          {t(notice, { email: email.trim() })}
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <p className="text-sm text-muted">{t(`login.subtitle.${mode}`)}</p>
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
            <TextButton onClick={() => void resend()} disabled={busy}>
              {t('login.resend')}
            </TextButton>
          )}
          <SubmitButton busy={busy}>{t(`login.submit.${mode}`)}</SubmitButton>
        </form>
      )}
      <nav className="flex flex-col items-start gap-2 border-t border-edge/70 pt-4">
        {mode === 'signin' ? (
          <>
            <TextButton onClick={() => switchTo('forgot')}>{t('login.to_forgot')}</TextButton>
            <TextButton onClick={() => switchTo('signup')}>{t('login.to_signup')}</TextButton>
          </>
        ) : (
          <TextButton onClick={() => switchTo('signin')}>{t('login.to_signin')}</TextButton>
        )}
      </nav>
    </AuthCard>
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
    <AuthCard title={t('login.title.reset')}>
      {!ready && <p className="text-sm text-muted">{t('login.busy')}</p>}
      {ready && !session && (
        <div className="space-y-3">
          <p className="text-sm text-muted">{t('login.reset_invalid')}</p>
          <Link href="/login" className="text-xs text-open">
            {t('header.sign_in')}
          </Link>
        </div>
      )}
      {ready && session && (
        <form onSubmit={onSubmit} className="space-y-4">
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
    </AuthCard>
  );
}

function AuthCard({ title, children }: { title: string; children: React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-sm space-y-6 py-6">
      <Link
        href="/"
        className="inline-flex rounded font-mono text-xs uppercase tracking-wider text-muted transition hover:text-open"
      >
        {t('login.back')}
      </Link>
      <section className="panel space-y-4 p-6">
        <h1 className="text-xl font-semibold tracking-tight text-slate-50">{title}</h1>
        {children}
      </section>
    </div>
  );
}

function Field({
  label,
  hint,
  ...input
}: { label: string; hint?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block space-y-1.5">
      <span className="font-mono text-[11px] uppercase tracking-wider text-muted">{label}</span>
      <input
        required
        {...input}
        className="w-full rounded-lg border border-edge bg-panel/80 px-3 py-2.5 font-mono text-sm text-slate-100"
      />
      {hint && <span className="block text-xs text-muted">{hint}</span>}
    </label>
  );
}

function AuthError({ code }: { code: string | null }) {
  const { t } = useTranslation();
  if (!code) return null;
  return (
    <p role="alert" className="text-sm text-tight">
      {t(ERROR_KEY[code] ?? 'login.error.generic')}
    </p>
  );
}

function SubmitButton({ busy, children }: { busy: boolean; children: React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <button
      type="submit"
      disabled={busy}
      className="w-full rounded-md border border-open bg-open/10 px-4 py-2.5 font-mono text-xs uppercase tracking-wider text-open transition hover:bg-open/20 disabled:opacity-50"
    >
      {busy ? t('login.busy') : children}
    </button>
  );
}

function TextButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className="text-left text-xs text-muted transition hover:text-open disabled:opacity-50"
    />
  );
}
