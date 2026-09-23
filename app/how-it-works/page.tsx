import type { Metadata } from 'next';

import { HowItWorks } from '@/components/HowItWorks';

const TITLE = 'How TrendPrint finds 3D prints that sell — buying demand, competition and margin';
const DESCRIPTION =
  'Find what to 3D print and sell: a daily opportunity score from real buying demand, competition and margin ' +
  'across online marketplaces and search trends. See which products still have room to sell — free account, no card.';

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  keywords: [
    'what to 3d print and sell',
    '3d printing business ideas',
    'best selling 3d prints',
    '3d print product research',
    'trending 3d prints',
    '3d print trends',
    'profitable 3d prints',
  ],
  alternates: { canonical: '/how-it-works' },
  openGraph: { title: TITLE, description: DESCRIPTION, url: '/how-it-works', type: 'article' },
  twitter: { card: 'summary', title: TITLE, description: DESCRIPTION },
};

// Perguntas frequentes em formato que o Google entende (FAQPage). As respostas
// dizem o mesmo que a pagina, em ingles, a lingua servida a quem chega sem
// preferencia guardada.
const FAQ = [
  [
    'What does TrendPrint measure?',
    'Which 3D-printable products have real buying demand in online marketplaces while the market is still open. It does not measure virality: a product everyone talks about but thousands of shops already sell scores low.',
  ],
  [
    'How is demand measured?',
    'By the reviews left in the last 30 days on the listing that leads the marketplace search for the product. Whoever reviews, bought — so it tracks purchases, not clicks or views.',
  ],
  [
    'How is the opportunity score calculated?',
    'Each signal is compared with products in the same category. The opportunity gap (demand minus competition) is worth 60%, the demand direction versus 7 days earlier 25%, and the median price of the top 25 listings 15%.',
  ],
  [
    'Is it free?',
    'Yes. A free account shows the best product in each category with its full score. Paid plans show the whole ranking and the listings behind each product.',
  ],
  [
    'Where does the data come from?',
    'From online marketplaces (listings, prices and recent reviews) and from search signals on Google and YouTube, collected every day. Nothing is invented: when a source fails, that signal is left out, not counted as zero.',
  ],
];

const faqJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQ.map(([question, answer]) => ({
    '@type': 'Question',
    name: question,
    acceptedAnswer: { '@type': 'Answer', text: answer },
  })),
};

export default function HowItWorksPage() {
  return (
    <>
      {/* Conteudo fixo, escrito aqui; nada vem do utilizador. */}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />
      <HowItWorks />
    </>
  );
}
