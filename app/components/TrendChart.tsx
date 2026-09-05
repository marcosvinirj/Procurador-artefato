import type { HistoryPoint } from '@/lib/types';

const WIDTH = 320;
const HEIGHT = 120;
const PAD = 8;

/** Cada serie tem a sua propria escala: interesse de pesquisa (0..100) e numero
 *  de listagens (milhares) nao partilham eixo. A base fica ancorada no zero de
 *  proposito — normalizar por min-max faria 3% de ruido parecer um colapso. */
function toPath(values: (number | null)[]): string | null {
  const points = values
    .map((value, index) => ({ value, index }))
    .filter((point): point is { value: number; index: number } => point.value !== null);
  if (points.length < 2) return null;

  const min = 0;
  const span = Math.max(...points.map((point) => point.value)) || 1;
  const stepX = (WIDTH - PAD * 2) / Math.max(1, values.length - 1);

  return points
    .map((point, position) => {
      const x = PAD + point.index * stepX;
      const y = HEIGHT - PAD - ((point.value - min) / span) * (HEIGHT - PAD * 2);
      return `${position === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
}

export function TrendChart({ history }: { history: HistoryPoint[] }) {
  const demand = toPath(history.map((point) => point.demand_raw));
  const competition = toPath(history.map((point) => point.competition_raw));

  if (!demand && !competition) {
    return (
      <p className="py-10 text-center text-sm text-muted">
        Ainda sem historico suficiente. A recolha diaria acumula um ponto por dia.
      </p>
    );
  }

  return (
    <figure>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Evolucao de procura e concorrencia ao longo de ${history.length} dias`}
      >
        {demand && <path d={demand} fill="none" stroke="#22d3a5" strokeWidth="2" />}
        {competition && (
          <path
            d={competition}
            fill="none"
            stroke="#f2545b"
            strokeWidth="2"
            strokeDasharray="4 3"
          />
        )}
      </svg>
      <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-muted">
        <span className="text-open">— procura</span>
        <span className="text-tight">--- concorrencia</span>
        <span>escalas independentes</span>
      </figcaption>
    </figure>
  );
}
