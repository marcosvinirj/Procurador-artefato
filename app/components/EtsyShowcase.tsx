'use client';

import { nameLabel, useTranslation } from '@/lib/i18n';
import type { Listing, ModelDetail } from '@/lib/types';

/** Os anuncios da Etsy por tras dos numeros. O servidor ja cortou o que o
 *  plano nao ve (api/index._showcase): aqui so se mostra o que chegou.
 *  A foto fica na Etsy — o site aponta para ela, nunca a copia. */
export function EtsyShowcase({ model }: { model: ModelDetail }) {
  const { t, locale } = useTranslation();
  const name = nameLabel(locale, model.name);
  const upsell = model.plan === 'free' ? 'showcase.upsell_free' : model.plan === 'pro' ? 'showcase.upsell_pro' : null;

  return (
    <section className="panel space-y-4 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="font-mono text-xs uppercase tracking-wider text-muted">
          {t(model.showcase.length > 1 ? 'showcase.title_many' : 'showcase.title_one')}
        </h2>
        {model.search_url && (
          <a
            href={model.search_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-open hover:underline"
          >
            {t('showcase.search')} ↗
          </a>
        )}
      </div>

      {model.showcase.length === 0 ? (
        <p className="text-sm text-muted">{t('showcase.empty')}</p>
      ) : (
        <ul className={`grid gap-3 ${model.showcase.length > 1 ? 'grid-cols-2 sm:grid-cols-4' : 'max-w-xs'}`}>
          {model.showcase.map((listing, index) => (
            <li key={listing.url ?? index}>
              <ListingCard listing={listing} fallbackAlt={name} />
            </li>
          ))}
        </ul>
      )}

      {upsell && <p className="border-t border-edge/70 pt-3 text-xs text-muted">{t(upsell)}</p>}
    </section>
  );
}

/** Moeda vinda da Etsy: se o codigo vier estranho, mostra o numero em vez de
 *  rebentar a pagina (Intl lanca excecao com um codigo de moeda invalido). */
function formatPrice(value: number, currency?: string | null): string {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: currency ?? 'USD' }).format(value);
  } catch {
    return value.toFixed(2);
  }
}

function ListingCard({ listing, fallbackAlt }: { listing: Listing; fallbackAlt: string }) {
  const { t } = useTranslation();
  const price = listing.price != null ? formatPrice(listing.price, listing.currency) : null;

  return (
    <div className="space-y-2">
      <div className="aspect-square overflow-hidden rounded-lg border border-edge bg-ink/60">
        {listing.image ? (
          // eslint-disable-next-line @next/next/no-img-element -- imagem da Etsy, servida pelo CDN deles
          <img
            src={listing.image}
            alt={listing.title ?? fallbackAlt}
            loading="lazy"
            referrerPolicy="no-referrer"
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center p-3 text-center text-xs text-muted">
            {t('showcase.no_photo')}
          </div>
        )}
      </div>
      {listing.title && <p className="line-clamp-2 text-xs leading-snug text-slate-200">{listing.title}</p>}
      <div className="flex items-center justify-between gap-2 font-mono text-[11px]">
        {price && <span className="text-slate-100">{price}</span>}
        {listing.url && (
          <a href={listing.url} target="_blank" rel="noopener noreferrer" className="text-open hover:underline">
            {t('showcase.view')} ↗
          </a>
        )}
      </div>
    </div>
  );
}
