'use client';

import { LOCALE_LABEL, LOCALES, useTranslation, type Locale } from '@/lib/i18n';

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useTranslation();

  return (
    <label className="flex items-center">
      <span className="sr-only">{t('header.language_label')}</span>
      <select
        value={locale}
        onChange={(event) => setLocale(event.target.value as Locale)}
        className="rounded-md border border-edge bg-panel/80 px-2 py-1 font-mono text-[11px] uppercase tracking-wider text-slate-200"
      >
        {LOCALES.map((code) => (
          <option key={code} value={code}>
            {LOCALE_LABEL[code]}
          </option>
        ))}
      </select>
    </label>
  );
}
