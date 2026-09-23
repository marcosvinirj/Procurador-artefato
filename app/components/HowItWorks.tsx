'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type FormEvent, type RefObject } from 'react';

import { SIGNUP_EMAIL_KEY } from '@/components/AuthForms';
import { OpportunityScale } from '@/components/OpportunityScale';
import { useAuth } from '@/lib/auth';
import { useTranslation, type Locale } from '@/lib/i18n';

/** Pagina publica "Como funciona" — e a porta de entrada do Google (o resto do
 *  site exige conta). Os numeros aqui espelham o codigo: pesos em
 *  core/scoring.WEIGHTS, janelas em core/sources e core/lifecycle. Mudar um sem
 *  o outro faz a pagina prometer o que o site nao faz. As animacoes nao mostram
 *  numeros de mercado: ilustram o que se mede, nunca inventam um resultado. */
type Visual = 'reviews' | 'listings' | 'prices' | 'trend';

interface Content {
  kicker: string;
  title: string;
  lead: string;
  searchLabel: string;
  emailLabel: string;
  signup: string;
  captureNote: string;
  haveAccount: string;
  termTitle: string;
  termExample: string;
  termBody: string;
  termProduct: string;
  termSearch: string;
  termSynonyms: string;
  signalsTitle: string;
  signals: { name: string; weight: string; caption: string; body: string; visual: Visual }[];
  midCta: string;
  midCtaLink: string;
  scoreTitle: string;
  scoreBody: string[];
  weights: [string, number][];
  dailyTitle: string;
  daily: string[];
  limitsTitle: string;
  limits: string[];
}

// Exemplo ilustrativo, de proposito FORA do catalogo: a pagina e publica e nao
// pode mostrar o que o ranking tem (isso e para quem tem conta).
const SEARCH_TERM = 'hanging planter';

const CONTENT: Record<Locale, Content> = {
  pt: {
    kicker: 'Como funciona',
    title: 'Não medimos o que está viral. Medimos o que está a vender — e onde ainda cabe mais um.',
    lead: 'Um produto pode estar em todo o lado no TikTok e mesmo assim ser má ideia: se já há milhares de lojas a vendê-lo, a atenção já foi apanhada por outros. O TrendPrint procura o contrário — procura de compra real com o mercado ainda aberto.',
    searchLabel: 'Pesquisa',
    emailLabel: 'O teu email',
    signup: 'Criar conta grátis',
    captureNote: 'Grátis e sem cartão. Vês já o melhor produto de cada categoria.',
    haveAccount: 'Já tens conta? Entra',
    termTitle: 'Cada produto é um termo de mercado',
    termExample: 'Exemplo',
    termBody: 'Não recomendamos o produto de uma loja específica. Recomendamos um tipo de produto, medido pela pesquisa exata que os compradores fazem nos marketplaces. O design é teu.',
    termProduct: 'Vaso Suspenso',
    termSearch: 'é a pesquisa',
    termSynonyms: 'mais os sinónimos, porque o mesmo produto vende com vários nomes',
    signalsTitle: 'Quatro sinais, recolhidos todos os dias',
    signals: [
      {
        name: 'Procura',
        weight: 'quem compra',
        caption: 'avaliações · últimos 30 dias',
        body: 'Avaliações deixadas no último mês no anúncio que lidera essa pesquisa. Quem avalia, comprou — por isso medimos compras, não cliques nem visualizações.',
        visual: 'reviews',
      },
      {
        name: 'Concorrência',
        weight: 'quem já vende',
        caption: 'anúncios na pesquisa',
        body: 'Quantos anúncios aparecem nessa pesquisa nos marketplaces. Muitos anúncios = mercado apertado, por muito procurado que seja.',
        visual: 'listings',
      },
      {
        name: 'Margem',
        weight: 'quanto se paga',
        caption: 'preço mediano · 25 primeiros',
        body: 'O preço mediano dos 25 primeiros anúncios. Diz se o produto vale a pena imprimir, depois de filamento e tempo de máquina.',
        visual: 'prices',
      },
      {
        name: 'Direção',
        weight: 'para onde vai',
        caption: 'hoje vs. 7 dias atrás',
        body: 'Se a procura está a subir ou a descer em relação a 7 dias antes. Procura alta mas em queda vale menos do que procura a nascer.',
        visual: 'trend',
      },
    ],
    midCta: 'Queres ver estes quatro sinais calculados em produtos reais?',
    midCtaLink: 'Cria conta grátis →',
    scoreTitle: 'Do sinal ao score',
    scoreBody: [
      'Cada sinal é comparado só com os produtos da mesma categoria: 300 anúncios saturam um nicho de utilidades, mas não são nada em decoração.',
      'O coração do score é o gap de oportunidade — procura menos concorrência. A direção e a margem desempatam.',
      'Quando uma fonte falha num dia, esse sinal não conta como zero: o peso passa para os outros. Nunca inventamos um número.',
    ],
    weights: [
      ['Gap de oportunidade', 60],
      ['Direção', 25],
      ['Margem', 15],
    ],
    dailyTitle: 'O que acontece enquanto dormes',
    daily: [
      'De madrugada, o site recolhe os sinais de cada produto nos marketplaces, no Google e no YouTube.',
      'Produtos que ficam saturados 5 dias seguidos saem do ranking sozinhos — e voltam se recuperarem. Um dia mau isolado não tira nada.',
      'Todos os dias procuramos produtos novos no que as pessoas pesquisam como impressão 3D e nas lojas que vigiamos. Nada entra no ranking sem revisão humana.',
    ],
    limitsTitle: 'O que não medimos (e dizemos)',
    limits: [
      'Visualizações de anúncios de outras lojas: só o dono as vê.',
      'Nem todo o comprador avalia, e a avaliação chega dias depois da venda. Serve para ritmo, não para contar vendas.',
      'Só vemos o que já está à venda nos marketplaces. O que explode no TikTok e ainda não chegou lá, ainda não aparece.',
      'Personagens com dono (anime, Marvel, jogos) não se podem vender impressos. Medimos o formato — chibi, busto, máscara — e o design tem de ser teu.',
    ],
  },
  en: {
    kicker: 'How it works',
    title: "We don't measure what's viral. We measure what's selling — and where there's still room for one more.",
    lead: 'A product can be all over TikTok and still be a bad idea: if thousands of shops already sell it, someone else has captured the attention. TrendPrint looks for the opposite — real buying demand while the market is still open.',
    searchLabel: 'Search',
    emailLabel: 'Your email',
    signup: 'Create free account',
    captureNote: 'Free, no card. See the best product in each category right away.',
    haveAccount: 'Have an account? Sign in',
    termTitle: 'Each product is a market term',
    termExample: 'Example',
    termBody: "We don't recommend one shop's specific product. We recommend a type of product, measured by the exact search buyers type on online marketplaces. The design is yours.",
    termProduct: 'Hanging Planter',
    termSearch: 'is the search',
    termSynonyms: 'plus synonyms, because the same product sells under several names',
    signalsTitle: 'Four signals, collected every day',
    signals: [
      {
        name: 'Demand',
        weight: 'who buys',
        caption: 'reviews · last 30 days',
        body: 'Reviews left in the last month on the listing that leads that search. Whoever reviews, bought — so we measure purchases, not clicks or views.',
        visual: 'reviews',
      },
      {
        name: 'Competition',
        weight: 'who already sells',
        caption: 'listings in the search',
        body: 'How many listings show up for that search on online marketplaces. Many listings = a crowded market, however popular it is.',
        visual: 'listings',
      },
      {
        name: 'Margin',
        weight: 'what people pay',
        caption: 'median price · top 25',
        body: 'The median price of the top 25 listings. It tells you whether the product is worth printing, after filament and machine time.',
        visual: 'prices',
      },
      {
        name: 'Direction',
        weight: 'where it is going',
        caption: 'today vs. 7 days ago',
        body: 'Whether demand is rising or falling compared with 7 days earlier. High demand that is falling is worth less than demand that is just starting.',
        visual: 'trend',
      },
    ],
    midCta: 'Want to see these four signals calculated on real products?',
    midCtaLink: 'Create a free account →',
    scoreTitle: 'From signal to score',
    scoreBody: [
      'Each signal is compared only with products in the same category: 300 listings saturate a utilities niche but are nothing in decor.',
      'The heart of the score is the opportunity gap — demand minus competition. Direction and margin break ties.',
      "When a source fails on a given day, that signal doesn't count as zero: its weight moves to the others. We never make up a number.",
    ],
    weights: [
      ['Opportunity gap', 60],
      ['Direction', 25],
      ['Margin', 15],
    ],
    dailyTitle: 'What happens while you sleep',
    daily: [
      "Overnight, the site collects each product's signals from online marketplaces, Google and YouTube.",
      'Products that stay saturated 5 days in a row leave the ranking on their own — and return if they recover. One bad day removes nothing.',
      'Every day we look for new products in what people search as 3D printing and in the shops we watch. Nothing enters the ranking without human review.',
    ],
    limitsTitle: "What we don't measure (and say so)",
    limits: [
      "Views of other shops' listings: only the owner sees them.",
      'Not every buyer leaves a review, and reviews arrive days after the sale. Good for pace, not for counting sales.',
      "We only see what is already for sale on marketplaces. Something blowing up on TikTok that hasn't reached them doesn't show yet.",
      "Characters someone owns (anime, Marvel, games) can't be sold printed. We measure the format — chibi, bust, mask — and the design has to be yours.",
    ],
  },
  es: {
    kicker: 'Cómo funciona',
    title: 'No medimos lo que es viral. Medimos lo que se vende — y dónde aún cabe uno más.',
    lead: 'Un producto puede estar en todo TikTok y aun así ser mala idea: si ya hay miles de tiendas vendiéndolo, otros ya captaron la atención. TrendPrint busca lo contrario — demanda de compra real con el mercado todavía abierto.',
    searchLabel: 'Búsqueda',
    emailLabel: 'Tu correo',
    signup: 'Crear cuenta gratis',
    captureNote: 'Gratis y sin tarjeta. Ves ya el mejor producto de cada categoría.',
    haveAccount: '¿Ya tienes cuenta? Entra',
    termTitle: 'Cada producto es un término de mercado',
    termExample: 'Ejemplo',
    termBody: 'No recomendamos el producto concreto de una tienda. Recomendamos un tipo de producto, medido por la búsqueda exacta que hacen los compradores en los marketplaces. El diseño es tuyo.',
    termProduct: 'Maceta Colgante',
    termSearch: 'es la búsqueda',
    termSynonyms: 'más los sinónimos, porque el mismo producto se vende con varios nombres',
    signalsTitle: 'Cuatro señales, recogidas cada día',
    signals: [
      {
        name: 'Demanda',
        weight: 'quién compra',
        caption: 'reseñas · últimos 30 días',
        body: 'Reseñas dejadas en el último mes en el anuncio que lidera esa búsqueda. Quien reseña, compró — por eso medimos compras, no clics ni visitas.',
        visual: 'reviews',
      },
      {
        name: 'Competencia',
        weight: 'quién ya vende',
        caption: 'anuncios en la búsqueda',
        body: 'Cuántos anuncios aparecen en esa búsqueda en los marketplaces. Muchos anuncios = mercado apretado, por muy buscado que sea.',
        visual: 'listings',
      },
      {
        name: 'Margen',
        weight: 'cuánto se paga',
        caption: 'precio mediano · 25 primeros',
        body: 'El precio mediano de los 25 primeros anuncios. Dice si vale la pena imprimirlo, tras filamento y tiempo de máquina.',
        visual: 'prices',
      },
      {
        name: 'Dirección',
        weight: 'hacia dónde va',
        caption: 'hoy vs. hace 7 días',
        body: 'Si la demanda sube o baja respecto a 7 días antes. Demanda alta pero en caída vale menos que demanda que está naciendo.',
        visual: 'trend',
      },
    ],
    midCta: '¿Quieres ver estas cuatro señales calculadas en productos reales?',
    midCtaLink: 'Crea una cuenta gratis →',
    scoreTitle: 'De la señal al puntaje',
    scoreBody: [
      'Cada señal se compara solo con productos de la misma categoría: 300 anuncios saturan un nicho de utilidades, pero no son nada en decoración.',
      'El corazón del puntaje es la brecha de oportunidad — demanda menos competencia. La dirección y el margen desempatan.',
      'Cuando una fuente falla un día, esa señal no cuenta como cero: su peso pasa a las demás. Nunca inventamos un número.',
    ],
    weights: [
      ['Brecha de oportunidad', 60],
      ['Dirección', 25],
      ['Margen', 15],
    ],
    dailyTitle: 'Lo que pasa mientras duermes',
    daily: [
      'De madrugada, el sitio recoge las señales de cada producto en los marketplaces, Google y YouTube.',
      'Los productos saturados 5 días seguidos salen solos del ranking — y vuelven si se recuperan. Un mal día aislado no quita nada.',
      'Cada día buscamos productos nuevos en lo que la gente busca como impresión 3D y en las tiendas que vigilamos. Nada entra al ranking sin revisión humana.',
    ],
    limitsTitle: 'Lo que no medimos (y lo decimos)',
    limits: [
      'Visitas de anuncios de otras tiendas: solo las ve el dueño.',
      'No todo comprador reseña, y la reseña llega días después de la venta. Sirve para ritmo, no para contar ventas.',
      'Solo vemos lo que ya está a la venta en los marketplaces. Lo que explota en TikTok y aún no llegó allí, todavía no aparece.',
      'Los personajes con dueño (anime, Marvel, juegos) no se pueden vender impresos. Medimos el formato — chibi, busto, máscara — y el diseño tiene que ser tuyo.',
    ],
  },
};

/** true a primeira vez que o elemento entra no ecra (e fica true). */
function useInView<T extends Element>(): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (!('IntersectionObserver' in window)) {
      setSeen(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { threshold: 0.2 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [seen]);
  return [ref, seen];
}

function Reveal({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const [ref, seen] = useInView<HTMLElement>();
  return (
    <section ref={ref} data-visible={seen} className={`reveal ${className}`}>
      {children}
    </section>
  );
}

const heading = 'text-lg font-semibold tracking-tight text-slate-50 sm:text-xl';
const delay = (seconds: number) => ({ animationDelay: `${seconds}s` });

export function HowItWorks() {
  const { locale } = useTranslation();
  const c = CONTENT[locale];

  return (
    <article className="mx-auto max-w-3xl space-y-16 py-4 sm:py-10">
      <header className="space-y-6">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-open">{c.kicker}</p>
        <h1 className="text-2xl font-semibold leading-tight tracking-tight text-slate-50 sm:text-4xl">{c.title}</h1>
        <p className="text-base leading-relaxed text-muted">{c.lead}</p>
        <SearchDemo c={c} />
        <SignupCapture c={c} />
      </header>

      <Reveal className="space-y-4">
        <h2 className={heading}>{c.termTitle}</h2>
        <p className="text-sm leading-relaxed text-muted">{c.termBody}</p>
        <div className="panel flex flex-wrap items-center gap-x-3 gap-y-2 p-5">
          <span className="w-full font-mono text-[11px] uppercase tracking-wider text-muted">{c.termExample}</span>
          <span className="font-medium text-slate-100">{c.termProduct}</span>
          <span className="text-sm text-muted">{c.termSearch}</span>
          <span className="chip border-open/50 text-slate-100">{SEARCH_TERM}</span>
          <span className="w-full text-xs text-muted">
            {c.termSynonyms}: <span className="font-mono">wall planter · hanging plant pot</span>
          </span>
        </div>
      </Reveal>

      <section className="space-y-4">
        <h2 className={heading}>{c.signalsTitle}</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {c.signals.map((signal) => (
            <SignalCard key={signal.visual} signal={signal} />
          ))}
        </div>
        <p className="pt-2 text-sm text-muted">
          {c.midCta}{' '}
          <Link href="/signup" className="font-medium text-open hover:underline">
            {c.midCtaLink}
          </Link>
        </p>
      </section>

      <ScoreSection c={c} />

      <Reveal className="space-y-4">
        <h2 className={heading}>{c.dailyTitle}</h2>
        <ol className="space-y-4 border-l border-edge pl-5">
          {c.daily.map((step, index) => (
            <li key={step} className="anim-pop relative text-sm leading-relaxed text-muted" style={delay(0.2 + index * 0.25)}>
              <span aria-hidden className="absolute -left-[25px] top-1.5 h-2 w-2 rounded-full bg-open" />
              {step}
            </li>
          ))}
        </ol>
      </Reveal>

      <Reveal className="space-y-4">
        <h2 className={heading}>{c.limitsTitle}</h2>
        <ul className="space-y-2">
          {c.limits.map((limit) => (
            <li key={limit} className="flex gap-3 text-sm leading-relaxed text-muted">
              <span aria-hidden className="text-mid">—</span>
              {limit}
            </li>
          ))}
        </ul>
      </Reveal>
    </article>
  );
}

/** A pesquisa a ser escrita, e os quatro sinais a acenderem: o que o site faz
 *  a cada produto, todos os dias. Sem movimento pedido, aparece ja completo. */
function SearchDemo({ c }: { c: Content }) {
  const [typed, setTyped] = useState(0);
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setTyped(SEARCH_TERM.length);
      return;
    }
    const timer = window.setInterval(() => {
      setTyped((n) => {
        if (n >= SEARCH_TERM.length) window.clearInterval(timer);
        return Math.min(n + 1, SEARCH_TERM.length);
      });
    }, 70);
    return () => window.clearInterval(timer);
  }, []);
  const done = typed >= SEARCH_TERM.length;

  return (
    <div aria-hidden className="panel space-y-4 p-4 sm:p-5" data-visible={done}>
      <div className="flex items-center gap-3 rounded-lg border border-edge bg-ink/70 px-4 py-3">
        <svg viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-muted" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="8.5" cy="8.5" r="5.5" />
          <path d="m13 13 4 4" strokeLinecap="round" />
        </svg>
        <span className="hidden font-mono text-[11px] uppercase tracking-wider text-muted sm:inline">{c.searchLabel}</span>
        <span className="font-mono text-sm text-slate-100">
          {SEARCH_TERM.slice(0, typed)}
          <span className="anim-caret ml-px inline-block h-4 w-[2px] translate-y-0.5 bg-open" />
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {c.signals.map((signal, index) => (
          <span key={signal.visual} className="anim-pop chip border-open/40 text-slate-200" style={delay(0.15 + index * 0.2)}>
            {signal.name}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Captura no topo: o email segue para o cadastro ja preenchido (por
 *  sessionStorage, nunca no link — um email no URL ficaria em historicos e
 *  registos de acesso). */
function SignupCapture({ c }: { c: Content }) {
  const { available } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');

  if (!available) return null;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      window.sessionStorage.setItem(SIGNUP_EMAIL_KEY, email.trim());
    } catch {
      // sem sessionStorage (janela privada): o cadastro abre so sem o email
    }
    router.push('/signup');
  }

  return (
    <div className="space-y-2">
      <form onSubmit={onSubmit} className="flex max-w-lg flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="capture-email">
          {c.emailLabel}
        </label>
        <input
          id="capture-email"
          type="email"
          required
          autoComplete="email"
          maxLength={254}
          placeholder={c.emailLabel}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="w-full flex-1 rounded-lg border border-edge bg-ink/70 px-4 py-3 text-base text-slate-100 placeholder:text-muted focus:border-open/60"
        />
        <button type="submit" className="btn-primary shrink-0">
          {c.signup}
        </button>
      </form>
      <p className="text-xs text-muted">
        {c.captureNote}{' '}
        <Link href="/login" className="text-slate-200 hover:text-open">
          {c.haveAccount}
        </Link>
      </p>
    </div>
  );
}

function SignalCard({ signal }: { signal: Content['signals'][number] }) {
  const [ref, seen] = useInView<HTMLDivElement>();
  return (
    <div ref={ref} data-visible={seen} className="reveal panel space-y-3 p-5">
      <div aria-hidden className="flex h-20 items-end justify-center rounded-lg border border-edge/60 bg-ink/50 px-4 pb-3 pt-4">
        {signal.visual === 'reviews' && <ReviewsVisual />}
        {signal.visual === 'listings' && <ListingsVisual />}
        {signal.visual === 'prices' && <PricesVisual />}
        {signal.visual === 'trend' && <TrendVisual />}
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="font-medium text-slate-100">{signal.name}</h3>
        <span className="font-mono text-[11px] uppercase tracking-wider text-open">{signal.weight}</span>
      </div>
      <p className="font-mono text-[11px] text-muted">{signal.caption}</p>
      <p className="text-sm leading-relaxed text-muted">{signal.body}</p>
    </div>
  );
}

/** Avaliacoes a chegar, uma a uma. */
function ReviewsVisual() {
  return (
    <div className="flex items-center gap-2">
      {[0, 1, 2, 3, 4].map((index) => (
        <svg key={index} viewBox="0 0 20 20" className="anim-pop h-7 w-7 text-open" style={delay(0.3 + index * 0.18)}>
          <path fill="currentColor" d="m10 1.8 2.5 5.3 5.8.7-4.3 4 1.1 5.7L10 14.7l-5.1 2.8 1.1-5.7-4.3-4 5.8-.7z" />
        </svg>
      ))}
    </div>
  );
}

/** A grelha de anuncios a encher: quanto mais cheia, mais apertado o mercado. */
function ListingsVisual() {
  return (
    <div className="grid grid-cols-12 gap-1">
      {Array.from({ length: 36 }, (_, index) => (
        <span
          key={index}
          className={`anim-lit h-2.5 w-2.5 rounded-sm ${index < 26 ? 'bg-tight/80' : 'bg-slate-600/60'}`}
          style={delay(0.2 + index * 0.03)}
        />
      ))}
    </div>
  );
}

/** Precos dos primeiros anuncios, ordenados; a mediana e a do meio. */
function PricesVisual() {
  const heights = [30, 42, 50, 58, 66, 78, 92];
  return (
    <div className="relative flex h-full items-end gap-2">
      {heights.map((height, index) => (
        <span
          key={height}
          className={`anim-grow-y w-4 rounded-t ${index === 3 ? 'bg-open' : 'bg-slate-600/70'}`}
          style={{ height: `${height}%`, ...delay(0.2 + index * 0.08) }}
        />
      ))}
      <span className="anim-grow-x absolute inset-x-0 border-t border-dashed border-open/70" style={{ bottom: '58%', ...delay(1) }} />
    </div>
  );
}

/** A procura dos ultimos dias, a subir. */
function TrendVisual() {
  return (
    <svg viewBox="0 0 160 56" className="h-full w-full max-w-[220px]">
      <polyline
        pathLength={1}
        className="anim-draw"
        style={delay(0.2)}
        fill="none"
        stroke="#22d3a5"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        points="4,46 26,42 48,44 70,34 92,36 114,22 136,16 156,8"
      />
      <circle className="anim-pop" style={delay(1.5)} cx="156" cy="8" r="4.5" fill="#22d3a5" />
    </svg>
  );
}

function ScoreSection({ c }: { c: Content }) {
  const [ref, seen] = useInView<HTMLElement>();
  return (
    <section ref={ref} data-visible={seen} className="reveal space-y-5">
      <h2 className={heading}>{c.scoreTitle}</h2>
      <div className="space-y-3">
        {c.scoreBody.map((paragraph) => (
          <p key={paragraph} className="text-sm leading-relaxed text-muted">
            {paragraph}
          </p>
        ))}
      </div>
      <div className="panel grid gap-8 p-6 sm:grid-cols-2 sm:items-center">
        <ul className="space-y-4">
          {c.weights.map(([label, value], index) => (
            <li key={label} className="space-y-1.5">
              <div className="flex items-baseline justify-between text-sm">
                <span className="text-slate-200">{label}</span>
                <span className="font-mono text-open">{value}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-edge">
                <div
                  className="anim-grow-x h-full rounded-full bg-open"
                  style={{ width: `${value}%`, ...delay(0.3 + index * 0.2) }}
                />
              </div>
            </li>
          ))}
        </ul>
        {/* So monta quando aparece: assim a "impressao" do medidor acontece a vista. */}
        <div className="flex min-h-[220px] items-center justify-center">{seen && <OpportunityScale />}</div>
      </div>
    </section>
  );
}
