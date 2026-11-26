import { useEffect, useMemo, useRef, useState } from "react";
import {
  FileText,
  LoaderCircle,
  Maximize2,
  Minus,
  Network,
  Plus,
} from "lucide-react";
import { api, humanizeError } from "../lib/api";
import type {
  GraphConcept,
  KnowledgeCard,
  KnowledgeGraph,
} from "../types";

type Props = {
  onOpenCard: (card: KnowledgeCard) => void;
};

type Point = {
  x: number;
  y: number;
};

type Layout = {
  width: number;
  height: number;
  communities: Array<{
    id: string;
    name: string;
    summary: string;
    x: number;
    y: number;
    width: number;
    height: number;
  }>;
  domains: Array<{ id: string; name: string; summary: string; point: Point }>;
  concepts: Array<GraphConcept & { point: Point }>;
  positions: Map<string, Point>;
};

function buildLayout(graph: KnowledgeGraph): Layout {
  const communities = [] as Layout["communities"];
  const domains = [] as Layout["domains"];
  const concepts = [] as Layout["concepts"];
  const positions = new Map<string, Point>();
  let y = 32;
  for (const community of graph.communities) {
    const communityDomains = graph.domains.filter(
      (domain) => domain.community_id === community.id,
    );
    const columns = Math.max(1, Math.min(2, communityDomains.length));
    const rows = Math.max(1, Math.ceil(communityDomains.length / columns));
    const cellWidth = 460;
    const cellHeight = 390;
    const height = 70 + rows * cellHeight;
    communities.push({
      ...community,
      x: 40,
      y,
      width: columns * cellWidth + 80,
      height,
    });
    communityDomains.forEach((domain, domainIndex) => {
      const column = domainIndex % columns;
      const row = Math.floor(domainIndex / columns);
      const domainPoint = {
        x: 80 + column * cellWidth + cellWidth / 2,
        y: y + 70 + row * cellHeight + cellHeight / 2,
      };
      domains.push({ ...domain, point: domainPoint });
      positions.set(domain.id, domainPoint);
      const domainConcepts = graph.concepts.filter(
        (concept) => concept.domain_id === domain.id,
      );
      domainConcepts.forEach((concept, index) => {
        const ring = Math.floor(index / 8);
        const ringIndex = index % 8;
        const ringCount = Math.min(8, domainConcepts.length - ring * 8);
        const angle = (ringIndex / ringCount) * Math.PI * 2 - Math.PI / 2;
        const radius = 138 + ring * 76;
        const point = {
          x: domainPoint.x + Math.cos(angle) * radius,
          y: domainPoint.y + Math.sin(angle) * radius,
        };
        concepts.push({ ...concept, point });
        positions.set(concept.id, point);
      });
    });
    y += height + 46;
  }
  return {
    width: Math.max(780, ...communities.map((item) => item.width + 80)),
    height: Math.max(560, y + 20),
    communities,
    domains,
    concepts,
    positions,
  };
}

export function GraphExplorer({ onOpenCard }: Props) {
  const [graph, setGraph] = useState<KnowledgeGraph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeConcept, setActiveConcept] = useState<string | null>(null);
  const [cards, setCards] = useState<Record<string, KnowledgeCard[]>>({});
  const [loadingCards, setLoadingCards] = useState<string | null>(null);
  const [scale, setScale] = useState(0.82);
  const [offset, setOffset] = useState({ x: 20, y: 20 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  useEffect(() => {
    api.getGraph().then(setGraph).catch((reason) => setError(humanizeError(reason)));
  }, []);

  const layout = useMemo(() => (graph ? buildLayout(graph) : null), [graph]);
  const relatedConcepts = useMemo(() => {
    if (!graph || !activeConcept) return null;
    const related = new Set([activeConcept]);
    for (const edge of graph.edges) {
      if (edge.source_id === activeConcept) related.add(edge.target_id);
      if (edge.target_id === activeConcept) related.add(edge.source_id);
    }
    return related;
  }, [activeConcept, graph]);

  async function revealCards(conceptId: string) {
    setActiveConcept(conceptId);
    if (cards[conceptId]) return;
    setLoadingCards(conceptId);
    try {
      const result = await api.getConceptCards(conceptId);
      setCards((current) => ({ ...current, [conceptId]: result }));
    } catch (reason) {
      setError(humanizeError(reason));
    } finally {
      setLoadingCards(null);
    }
  }

  function resetViewport() {
    setScale(0.82);
    setOffset({ x: 20, y: 20 });
  }

  if (error && !graph) {
    return <div className="graph-state inline-alert">{error}</div>;
  }

  if (!graph || !layout) {
    return (
      <div className="graph-state">
        <LoaderCircle className="spin" size={24} /> Загружаем карту знаний
      </div>
    );
  }

  if (!graph.concepts.length) {
    return (
      <div className="graph-state graph-state--empty">
        <span><Network size={25} /></span>
        <h2>Граф пока пуст</h2>
        <p>Загрузите и обработайте первый документ, чтобы появились домены и концепции.</p>
      </div>
    );
  }

  return (
    <section className="graph-view">
      <header className="graph-heading">
        <div>
          <p className="eyebrow">Карта знаний</p>
          <h1>Граф знаний</h1>
          <p>Домены объединяют концепции. Наведите на концепцию, чтобы увидеть связанные документы.</p>
        </div>
        <div className="graph-legend">
          <span><i className="legend-domain" /> Домен</span>
          <span><i className="legend-concept" /> Концепция</span>
          <span>{graph.concepts.length} концепций</span>
        </div>
      </header>
      {error && <div className="inline-alert graph-alert">{error}</div>}
      <div
        className="graph-canvas"
        onPointerDown={(event) => {
          if ((event.target as Element).closest("button")) return;
          drag.current = { x: event.clientX, y: event.clientY, ox: offset.x, oy: offset.y };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          setOffset({
            x: drag.current.ox + event.clientX - drag.current.x,
            y: drag.current.oy + event.clientY - drag.current.y,
          });
        }}
        onPointerUp={() => { drag.current = null; }}
        onPointerCancel={() => { drag.current = null; }}
        onWheel={(event) => {
          event.preventDefault();
          setScale((value) => Math.min(1.35, Math.max(0.48, value - event.deltaY * 0.001)));
        }}
      >
        <div className="graph-controls">
          <button onClick={() => setScale((value) => Math.min(1.35, value + 0.12))} aria-label="Увеличить"><Plus size={17} /></button>
          <button onClick={() => setScale((value) => Math.max(0.48, value - 0.12))} aria-label="Уменьшить"><Minus size={17} /></button>
          <button onClick={resetViewport} aria-label="Сбросить масштаб"><Maximize2 size={16} /></button>
        </div>
        <svg
          className="graph-stage"
          width={layout.width}
          height={layout.height}
          style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})` }}
        >
          {layout.communities.map((community) => (
            <g key={community.id} className="community-region">
              <text x={community.x + 25} y={community.y + 34}>{community.name}</text>
              <title>{community.summary}</title>
            </g>
          ))}
          {graph.edges.map((edge) => {
            const source = layout.positions.get(edge.source_id);
            const target = layout.positions.get(edge.target_id);
            if (!source || !target) return null;
            const highlighted = activeConcept === edge.source_id || activeConcept === edge.target_id;
            return <line key={`${edge.source_id}-${edge.target_id}`} className={`concept-edge${highlighted ? " is-active" : activeConcept ? " is-muted" : ""}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />;
          })}
          {layout.concepts.map((concept) => {
            const domain = layout.positions.get(concept.domain_id);
            return domain ? <line key={`domain-${concept.id}`} className={`domain-edge${activeConcept === concept.id ? " is-active" : activeConcept ? " is-muted" : ""}`} x1={domain.x} y1={domain.y} x2={concept.point.x} y2={concept.point.y} /> : null;
          })}
          {layout.domains.map((domain) => (
            <foreignObject key={domain.id} x={domain.point.x - 125} y={domain.point.y - 45} width="250" height="90">
              <div className="domain-node">
                <strong>{domain.name}</strong>
                <small>{domain.summary}</small>
              </div>
            </foreignObject>
          ))}
          {layout.concepts.map((concept) => (
            <foreignObject key={concept.id} x={concept.point.x - 80} y={concept.point.y - 30} width="160" height="60">
              <button
                className={`concept-node${activeConcept === concept.id ? " is-active" : relatedConcepts?.has(concept.id) ? " is-related" : relatedConcepts ? " is-muted" : ""}`}
                title={concept.summary}
                onPointerEnter={() => void revealCards(concept.id)}
                onFocus={() => void revealCards(concept.id)}
                onClick={() => void revealCards(concept.id)}
              >
                <strong>{concept.name}</strong>
                <small>{concept.card_count} {concept.card_count === 1 ? "карточка" : "карточек"}</small>
              </button>
            </foreignObject>
          ))}
          {activeConcept && layout.positions.get(activeConcept) && (
            <foreignObject
              x={Math.min(layout.width - 330, layout.positions.get(activeConcept)!.x + 92)}
              y={Math.max(35, layout.positions.get(activeConcept)!.y - 58)}
              width="310"
              height="230"
              className="card-reveal-wrap"
              onPointerLeave={() => setActiveConcept(null)}
            >
              <div className="card-reveal">
                <span className="card-reveal-title">Связанные карточки</span>
                {loadingCards === activeConcept ? (
                  <span className="card-reveal-loading"><LoaderCircle className="spin" size={17} /> Загружаем</span>
                ) : (
                  cards[activeConcept]?.map((card) => (
                    <button key={card.id} onClick={() => onOpenCard(card)}>
                      <FileText size={17} />
                      <span><strong>{card.filename}</strong><small>{card.analysis.summary}</small></span>
                    </button>
                  ))
                )}
              </div>
            </foreignObject>
          )}
        </svg>
      </div>
    </section>
  );
}
