'use client';

import { OpportunityScale } from '@/components/OpportunityScale';
import { useTranslation, type Locale } from '@/lib/i18n';

/** Pagina publica "Como funciona". Os numeros aqui espelham o codigo — pesos
 *  em core/scoring.WEIGHTS, janelas em core/sources e core/lifecycle. Mudar
 *  um sem o outro faz a pagina prometer o que o site nao faz. Texto longo por
 *  idioma fica aqui, e nao no dicionario de i18n, para se ler como um todo. */
interface Content {
  kicker: string;
  title: string;
  lead: string;
  termTitle: string;
  termBody: string;
  termProduct: string;
  termSearch: string;
  termSynonyms: string;
  signalsTitle: string;
  signals: { name: string; weight: string; body: string }[];
  scoreTitle: string;
  scoreBody: string[];
  dailyTitle: string;
  daily: string[];
  limitsTitle: string;
  limits: string[];
}

const CONTENT: Record<Locale, Content> = {
  pt: {
    kicker: 'Como funciona',
    title: 'Não medimos o que está viral. Medimos o que está a vender — e onde ainda cabe mais um.',
    lead: 'Um produto pode estar em todo o lado no TikTok e mesmo assim ser má ideia: se já há milhares de lojas a vendê-lo, a atenção já foi apanhada por outros. O TrendPrint procura o contrário — procura de compra real com o mercado ainda aberto.',
    termTitle: 'Cada produto é um termo de mercado',
    termBody: 'Não recomendamos um dragão específico de uma loja. Recomendamos um tipo de produto, medido pela pesquisa exata que os compradores fazem na Etsy. O design é teu.',
    termProduct: 'Estátua de Dragão',
    termSearch: 'é a pesquisa',
    termSynonyms: 'mais os sinónimos, porque o mesmo produto vende com vários nomes',
    signalsTitle: 'Quatro sinais, recolhidos todos os dias',
    signals: [
      {
        name: 'Procura',
        weight: 'quem compra',
        body: 'Avaliações deixadas no último mês no anúncio que lidera essa pesquisa. Quem avalia, comprou — por isso medimos compras, não cliques nem visualizações.',
      },
      {
        name: 'Concorrência',
        weight: 'quem já vende',
        body: 'Quantos anúncios aparecem nessa pesquisa na Etsy. Muitos anúncios = mercado apertado, por muito procurado que seja.',
      },
      {
        name: 'Margem',
        weight: 'quanto se paga',
        body: 'O preço mediano dos 25 primeiros anúncios. Diz se o produto vale a pena imprimir, depois de filamento e tempo de máquina.',
      },
      {
        name: 'Direção',
        weight: 'para onde vai',
        body: 'Se a procura está a subir ou a descer em relação a 7 dias antes. Procura alta mas em queda vale menos do que procura a nascer.',
      },
    ],
    scoreTitle: 'Do sinal ao score',
    scoreBody: [
      'Cada sinal é comparado só com os produtos da mesma categoria: 300 anúncios saturam um nicho de utilidades, mas não são nada em decoração.',
      'O coração do score é o gap de oportunidade — procura menos concorrência — e vale 60%. A direção vale 25% e a margem 15%, para desempatar.',
      'Quando uma fonte falha num dia, esse sinal não conta como zero: o peso passa para os outros. Nunca inventamos um número.',
    ],
    dailyTitle: 'O que acontece enquanto dormes',
    daily: [
      'De madrugada, o site recolhe os sinais de cada produto na Etsy, no Google e no YouTube.',
      'Produtos que ficam saturados 5 dias seguidos saem do ranking sozinhos — e voltam se recuperarem. Um dia mau isolado não tira nada.',
      'Todos os dias procuramos produtos novos no que as pessoas pesquisam como impressão 3D e nas lojas que vigiamos. Nada entra no ranking sem revisão humana.',
    ],
    limitsTitle: 'O que não medimos (e dizemos)',
    limits: [
      'Visualizações de anúncios de outras lojas: só o dono as vê.',
      'Nem todo o comprador avalia, e a avaliação chega dias depois da venda. Serve para ritmo, não para contar vendas.',
      'Só vemos o que já vende na Etsy. O que explode no TikTok e ainda não chegou lá, ainda não aparece.',
      'Personagens com dono (anime, Marvel, jogos) não se podem vender impressos. Medimos o formato — chibi, busto, máscara — e o design tem de ser teu.',
    ],
  },
  en: {
    kicker: 'How it works',
    title: "We don't measure what's viral. We measure what's selling — and where there's still room for one more.",
    lead: "A product can be all over TikTok and still be a bad idea: if thousands of shops already sell it, someone else has captured the attention. TrendPrint looks for the opposite — real buying demand while the market is still open.",
    termTitle: 'Each product is a market term',
    termBody: "We don't recommend one shop's specific dragon. We recommend a type of product, measured by the exact search buyers type on Etsy. The design is yours.",
    termProduct: 'Dragon Statue',
    termSearch: 'is the search',
    termSynonyms: 'plus synonyms, because the same product sells under several names',
    signalsTitle: 'Four signals, collected every day',
    signals: [
      {
        name: 'Demand',
        weight: 'who buys',
        body: 'Reviews left in the last month on the listing that leads that search. Whoever reviews, bought — so we measure purchases, not clicks or views.',
      },
      {
        name: 'Competition',
        weight: 'who already sells',
        body: 'How many listings show up for that search on Etsy. Many listings = a crowded market, however popular it is.',
      },
      {
        name: 'Margin',
        weight: 'what people pay',
        body: 'The median price of the top 25 listings. It tells you whether the product is worth printing, after filament and machine time.',
      },
      {
        name: 'Direction',
        weight: 'where it is going',
        body: 'Whether demand is rising or falling compared with 7 days earlier. High demand that is falling is worth less than demand that is just starting.',
      },
    ],
    scoreTitle: 'From signal to score',
    scoreBody: [
      'Each signal is compared only with products in the same category: 300 listings saturate a utilities niche but are nothing in decor.',
      'The heart of the score is the opportunity gap — demand minus competition — worth 60%. Direction is 25% and margin 15%, as a tiebreaker.',
      "When a source fails on a given day, that signal doesn't count as zero: its weight moves to the others. We never make up a number.",
    ],
    dailyTitle: 'What happens while you sleep',
    daily: [
      'Overnight, the site collects each product’s signals from Etsy, Google and YouTube.',
      'Products that stay saturated 5 days in a row leave the ranking on their own — and return if they recover. One bad day removes nothing.',
      'Every day we look for new products in what people search as 3D printing and in the shops we watch. Nothing enters the ranking without human review.',
    ],
    limitsTitle: "What we don't measure (and say so)",
    limits: [
      "Views of other shops' listings: only the owner sees them.",
      'Not every buyer leaves a review, and reviews arrive days after the sale. Good for pace, not for counting sales.',
      "We only see what already sells on Etsy. Something blowing up on TikTok that hasn't reached Etsy doesn't show yet.",
      "Characters someone owns (anime, Marvel, games) can't be sold printed. We measure the format — chibi, bust, mask — and the design has to be yours.",
    ],
  },
  es: {
    kicker: 'Cómo funciona',
    title: 'No medimos lo que es viral. Medimos lo que se vende — y dónde aún cabe uno más.',
    lead: 'Un producto puede estar en todo TikTok y aun así ser mala idea: si ya hay miles de tiendas vendiéndolo, otros ya captaron la atención. TrendPrint busca lo contrario — demanda de compra real con el mercado todavía abierto.',
    termTitle: 'Cada producto es un término de mercado',
    termBody: 'No recomendamos el dragón concreto de una tienda. Recomendamos un tipo de producto, medido por la búsqueda exacta que hacen los compradores en Etsy. El diseño es tuyo.',
    termProduct: 'Estatua de Dragón',
    termSearch: 'es la búsqueda',
    termSynonyms: 'más los sinónimos, porque el mismo producto se vende con varios nombres',
    signalsTitle: 'Cuatro señales, recogidas cada día',
    signals: [
      {
        name: 'Demanda',
        weight: 'quién compra',
        body: 'Reseñas dejadas en el último mes en el anuncio que lidera esa búsqueda. Quien reseña, compró — por eso medimos compras, no clics ni visitas.',
      },
      {
        name: 'Competencia',
        weight: 'quién ya vende',
        body: 'Cuántos anuncios aparecen en esa búsqueda en Etsy. Muchos anuncios = mercado apretado, por muy buscado que sea.',
      },
      {
        name: 'Margen',
        weight: 'cuánto se paga',
        body: 'El precio mediano de los 25 primeros anuncios. Dice si vale la pena imprimirlo, tras filamento y tiempo de máquina.',
      },
      {
        name: 'Dirección',
        weight: 'hacia dónde va',
        body: 'Si la demanda sube o baja respecto a 7 días antes. Demanda alta pero en caída vale menos que demanda que está naciendo.',
      },
    ],
    scoreTitle: 'De la señal al puntaje',
    scoreBody: [
      'Cada señal se compara solo con productos de la misma categoría: 300 anuncios saturan un nicho de utilidades, pero no son nada en decoración.',
      'El corazón del puntaje es la brecha de oportunidad — demanda menos competencia — y vale 60%. La dirección vale 25% y el margen 15%, para desempatar.',
      'Cuando una fuente falla un día, esa señal no cuenta como cero: su peso pasa a las demás. Nunca inventamos un número.',
    ],
    dailyTitle: 'Lo que pasa mientras duermes',
    daily: [
      'De madrugada, el sitio recoge las señales de cada producto en Etsy, Google y YouTube.',
      'Los productos saturados 5 días seguidos salen solos del ranking — y vuelven si se recuperan. Un mal día aislado no quita nada.',
      'Cada día buscamos productos nuevos en lo que la gente busca como impresión 3D y en las tiendas que vigilamos. Nada entra al ranking sin revisión humana.',
    ],
    limitsTitle: 'Lo que no medimos (y lo decimos)',
    limits: [
      'Visitas de anuncios de otras tiendas: solo las ve el dueño.',
      'No todo comprador reseña, y la reseña llega días después de la venta. Sirve para ritmo, no para contar ventas.',
      'Solo vemos lo que ya se vende en Etsy. Lo que explota en TikTok y aún no llegó allí, todavía no aparece.',
      'Los personajes con dueño (anime, Marvel, juegos) no se pueden vender impresos. Medimos el formato — chibi, busto, máscara — y el diseño tiene que ser tuyo.',
    ],
  },
};

const heading = 'text-lg font-semibold tracking-tight text-slate-50 sm:text-xl';

export function HowItWorks() {
  const { locale } = useTranslation();
  const c = CONTENT[locale];

  return (
    <article className="mx-auto max-w-3xl space-y-14 py-4 sm:py-10">
      <header className="space-y-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-open">{c.kicker}</p>
        <h1 className="text-2xl font-semibold leading-tight tracking-tight text-slate-50 sm:text-4xl">{c.title}</h1>
        <p className="text-base leading-relaxed text-muted">{c.lead}</p>
      </header>

      <section className="space-y-4">
        <h2 className={heading}>{c.termTitle}</h2>
        <p className="text-sm leading-relaxed text-muted">{c.termBody}</p>
        <div className="panel flex flex-wrap items-center gap-x-3 gap-y-2 p-5">
          <span className="font-medium text-slate-100">{c.termProduct}</span>
          <span className="text-sm text-muted">{c.termSearch}</span>
          <span className="chip border-open/50 text-slate-100">fantasy dragon statue</span>
          <span className="w-full text-xs text-muted">
            {c.termSynonyms}: <span className="font-mono">dragon figurine · dragon sculpture</span>
          </span>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className={heading}>{c.signalsTitle}</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {c.signals.map((signal) => (
            <div key={signal.name} className="panel space-y-2 p-5">
              <div className="flex items-baseline justify-between gap-3">
                <h3 className="font-medium text-slate-100">{signal.name}</h3>
                <span className="font-mono text-[11px] uppercase tracking-wider text-open">{signal.weight}</span>
              </div>
              <p className="text-sm leading-relaxed text-muted">{signal.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-5">
        <h2 className={heading}>{c.scoreTitle}</h2>
        <div className="space-y-3">
          {c.scoreBody.map((paragraph) => (
            <p key={paragraph} className="text-sm leading-relaxed text-muted">
              {paragraph}
            </p>
          ))}
        </div>
        <div className="panel p-6">
          <OpportunityScale />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className={heading}>{c.dailyTitle}</h2>
        <ol className="space-y-3 border-l border-edge pl-5">
          {c.daily.map((step) => (
            <li key={step} className="relative text-sm leading-relaxed text-muted">
              <span aria-hidden className="absolute -left-[25px] top-1.5 h-2 w-2 rounded-full bg-open" />
              {step}
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-4">
        <h2 className={heading}>{c.limitsTitle}</h2>
        <ul className="space-y-2">
          {c.limits.map((limit) => (
            <li key={limit} className="flex gap-3 text-sm leading-relaxed text-muted">
              <span aria-hidden className="text-mid">—</span>
              {limit}
            </li>
          ))}
        </ul>
      </section>

    </article>
  );
}
