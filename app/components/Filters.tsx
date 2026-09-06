'use client';

import { categoryLabel, useTranslation } from '@/lib/i18n';

interface FiltersProps {
  query: string;
  onQuery: (value: string) => void;
  categories: string[];
  active: string | null;
  onCategory: (value: string | null) => void;
}

export function Filters({ query, onQuery, categories, active, onCategory }: FiltersProps) {
  const { t, locale } = useTranslation();

  return (
    <div className="flex flex-col gap-3">
      <label className="block">
        <span className="sr-only">{t('filters.search')}</span>
        <input
          type="search"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder={t('filters.search')}
          className="w-full rounded-lg border border-edge bg-panel/80 px-3 py-2.5 font-mono text-sm text-slate-100 placeholder:text-muted"
        />
      </label>

      <div className="flex flex-wrap gap-2" role="group" aria-label={t('filters.category_aria')}>
        <CategoryButton active={active === null} onClick={() => onCategory(null)}>
          {t('filters.all')}
        </CategoryButton>
        {categories.map((category) => (
          <CategoryButton
            key={category}
            active={active === category}
            onClick={() => onCategory(active === category ? null : category)}
          >
            {categoryLabel(locale, category)}
          </CategoryButton>
        ))}
      </div>
    </div>
  );
}

function CategoryButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-wider transition ${
        active
          ? 'border-open bg-open/10 text-open'
          : 'border-edge text-muted hover:border-muted hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  );
}
