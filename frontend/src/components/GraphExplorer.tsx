import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FileText, LoaderCircle, Maximize2, Minus, Network, Plus, Search, X } from "lucide-react";
import { api, humanizeError } from "../lib/api";
import { createLayout, relaxLayout, type GraphLayout } from "../lib/graphLayout";
import type { KnowledgeCard, KnowledgeGraph } from "../types";

type Props = { onOpenCard: (card: KnowledgeCard) => void };
export function GraphExplorer({ onOpenCard }: Props) {
  const [graph, setGraph] = useState<KnowledgeGraph | null>(null);
  const [layout, setLayout] = useState<GraphLayout | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [labels, setLabels] = useState(false);
  const [cards, setCards] = useState<Record<string, KnowledgeCard[]>>({});
  const [pending, setPending] = useState<Set<string>>(new Set());
  const requests = useRef(new Set<string>());
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const canvas = useRef<HTMLDivElement>(null);
  const drag = useRef<{ id: string | null; x: number; y: number; moved: boolean } | null>(null);

  useEffect(() => {
    let alive = true;
    api.getGraph().then((data) => { if (alive) setGraph(data); })
      .catch((reason) => { if (alive) setError(humanizeError(reason)); });
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    if (!graph) return;
    const next = createLayout(graph);
    let step = 0, frame = 0;
    function tick() {
      for (let i = 0; i < 4; i++, step++) relaxLayout(next, 1 - step / 240);
      if (step < 160) frame = requestAnimationFrame(tick);
      else setLayout(next);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [graph]);
  const fit = useCallback(() => {
    if (!canvas.current || !layout?.nodes.length) return;
    const { width, height } = canvas.current.getBoundingClientRect();
    const xs = layout.nodes.map((n) => n.x), ys = layout.nodes.map((n) => n.y);
    const left = Math.min(...xs) - 70, right = Math.max(...xs) + 70;
    const top = Math.min(...ys) - 70, bottom = Math.max(...ys) + 70;
    const scale = Math.max(0.05, Math.min(1.5, (width - 40) / (right - left), (height - 100) / (bottom - top)));
    setView({ scale, x: width / 2 - (left + right) / 2 * scale, y: height / 2 - (top + bottom) / 2 * scale });
  }, [layout]);
  const fitRef = useRef(fit);
  fitRef.current = fit;
  const ready = Boolean(layout);
  useEffect(() => {
    if (!canvas.current || !ready) return;
    const observer = new ResizeObserver(() => fitRef.current());
    observer.observe(canvas.current);
    return () => observer.disconnect();
  }, [ready]);
  function zoom(factor: number, x?: number, y?: number) {
    const bounds = canvas.current?.getBoundingClientRect();
    const px = x ?? (bounds?.width ?? 800) / 2, py = y ?? (bounds?.height ?? 600) / 2;
    setView((old) => {
      const scale = Math.max(0.05, Math.min(4, old.scale * factor));
      return { scale, x: px - (px - old.x) * scale / old.scale, y: py - (py - old.y) * scale / old.scale };
    });
  }
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      if ((event.target as Element).closest(".graph-inspector")) return;
      event.preventDefault();
      const bounds = element.getBoundingClientRect();
      zoom(Math.exp(-event.deltaY * 0.0015), event.clientX - bounds.left, event.clientY - bounds.top);
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [ready]);
  const focus = hovered ?? selected;
  const neighbors = useMemo(() => {
    const result = new Set<string>();
    if (focus) {
      result.add(focus);
      for (const edge of layout?.links ?? []) {
        if (edge.source === focus) result.add(edge.target);
        if (edge.target === focus) result.add(edge.source);
      }
    }
    return result;
  }, [focus, layout]);
  const positions = useMemo(() => new Map(layout?.nodes.map((n) => [n.id, n]) ?? []), [layout]);
  const active = selected ? positions.get(selected) : undefined;
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const matches = (name: string) => name.toLocaleLowerCase().includes(normalizedQuery);
  async function selectNode(id: string) {
    setSelected(id); setError("");
    if (positions.get(id)?.kind !== "concept" || cards[id] || requests.current.has(id)) return;
    requests.current.add(id);
    setPending((old) => new Set(old).add(id));
    try {
      const result = await api.getConceptCards(id);
      setCards((old) => ({ ...old, [id]: result }));
    } catch (reason) { setError(humanizeError(reason)); }
    finally {
      requests.current.delete(id);
      setPending((old) => { const next = new Set(old); next.delete(id); return next; });
    }
  }
  if (error && !graph) return <div className="graph-state inline-alert">{error}</div>;
  if (!layout || !graph) return <div className="graph-state"><LoaderCircle className="spin" size={24} /> Раскладываем граф знаний</div>;
  if (!layout.nodes.length) return <div className="graph-state graph-state--empty"><Network size={25} /><h2>Граф пока пуст</h2><p>Загрузите первый документ, чтобы появились связи.</p></div>;
  return (
    <section className="graph-view">
      <header className="graph-heading">
        <div><p className="eyebrow">Карта знаний</p><h1>Граф знаний</h1><p>Выберите узел, чтобы изучить его связи и документы.</p></div>
        <div className="graph-legend"><span><i className="legend-domain" /> Домен</span><span><i className="legend-concept" /> Концепция</span><span>{graph.concepts.length} концепций</span></div>
      </header>
      {error && <div className="inline-alert graph-alert" role="alert">{error}</div>}
      <div ref={canvas} className="graph-canvas graph-canvas--network">
        <div className="graph-toolbar">
          <label className="graph-search"><Search size={16} /><input aria-label="Найти узел" placeholder="Найти узел…" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
          <label className="graph-label-toggle"><input type="checkbox" checked={labels} onChange={(e) => setLabels(e.target.checked)} /> Подписи</label>
          {normalizedQuery && <small role="status">Найдено: {layout.nodes.filter((n) => matches(n.name)).length}</small>}
        </div>
        <div className="graph-controls">
          <button onClick={() => zoom(1.25)} aria-label="Увеличить"><Plus size={17} /></button>
          <button onClick={() => zoom(0.8)} aria-label="Уменьшить"><Minus size={17} /></button>
          <button onClick={fit} aria-label="Показать весь граф"><Maximize2 size={17} /></button>
        </div>
        <svg className="network-stage" aria-label="Связи базы знаний"
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            const id = (e.target as Element).closest("[data-node]")?.getAttribute("data-node") ?? null;
            drag.current = { id, x: e.clientX, y: e.clientY, moved: false };
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            const state = drag.current;
            if (!state) return;
            const dx = e.clientX - state.x, dy = e.clientY - state.y;
            if (!state.moved && Math.hypot(dx, dy) < 4) return;
            state.moved = true; state.x = e.clientX; state.y = e.clientY;
            if (state.id) setLayout((old) => old && ({ ...old, nodes: old.nodes.map((n) => n.id === state.id ? { ...n, x: n.x + dx / view.scale, y: n.y + dy / view.scale } : n) }));
            else setView((old) => ({ ...old, x: old.x + dx, y: old.y + dy }));
          }}
          onPointerUp={(e) => {
            const state = drag.current;
            if (state && !state.moved) {
              if (state.id) void selectNode(state.id);
              else setSelected(null);
            }
            drag.current = null;
            e.currentTarget.releasePointerCapture(e.pointerId);
          }}
          onPointerCancel={() => { drag.current = null; }}
          onLostPointerCapture={() => { drag.current = null; }}
        >
          <g transform={"translate(" + view.x + "," + view.y + ") scale(" + view.scale + ")"}>
            {layout.links.map((edge, i) => {
              const a = positions.get(edge.source)!, b = positions.get(edge.target)!;
              const highlighted = edge.source === focus || edge.target === focus;
              return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={"network-edge" + (edge.domain ? " network-edge--domain" : "") + (highlighted ? " is-active" : focus ? " is-muted" : "")} />;
            })}
            {layout.nodes.map((node) => {
              const highlighted = neighbors.has(node.id);
              const muted = (Boolean(focus) && !highlighted) || (Boolean(normalizedQuery) && !matches(node.name));
              const showLabel = labels || highlighted || (Boolean(normalizedQuery) && matches(node.name)) || (layout.nodes.length < 40 && view.scale >= 0.7) || view.scale > 1.8;
              const radius = node.kind === "domain" ? 6 : Math.min(7, 3.5 + Math.log2(node.count + 1) * 0.6);
              return <g key={node.id} data-node={node.id} transform={"translate(" + node.x + "," + node.y + ")"} tabIndex={0} role="button" aria-label={node.name + (node.kind === "domain" ? ", домен" : ", карточек: " + node.count)} aria-pressed={selected === node.id}
                className={"network-node network-node--" + node.kind + (muted ? " is-muted" : "") + (node.id === focus ? " is-active" : "")}
                onPointerEnter={() => { if (!drag.current) setHovered(node.id); }} onPointerLeave={() => setHovered(null)}
                onFocus={() => setHovered(node.id)} onBlur={() => setHovered(null)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); void selectNode(node.id); } }}>
                <title>{node.name + ": " + node.summary}</title>
                <circle className="network-hit" r={Math.max(12, 12 / view.scale)} />
                <circle className="network-dot" r={radius} />
                {showLabel && <text y={radius + 14} textAnchor="middle">{node.name.length > 32 ? node.name.slice(0, 31) + "…" : node.name}</text>}
              </g>;
            })}
          </g>
        </svg>
        {active && <aside className="graph-inspector" aria-label="Сведения об узле">
          <button className="graph-inspector-close" onClick={() => { setSelected(null); setHovered(null); }} aria-label="Закрыть сведения"><X size={18} /></button>
          <small>{active.kind === "domain" ? "Домен" : "Концепция"}</small><h2>{active.name}</h2><p>{active.summary}</p>
          {active.kind === "concept" && <div className="card-reveal">
            <span className="card-reveal-title">Связанные документы</span>
            {pending.has(active.id) ? <span className="card-reveal-loading"><LoaderCircle className="spin" size={17} /> Загружаем</span> : cards[active.id]?.length === 0 ? <p>Связанных документов пока нет.</p> : cards[active.id]?.map((card) => <button key={card.id} onClick={() => onOpenCard(card)}><FileText size={17} /><span><strong>{card.filename}</strong><small>{card.analysis.summary}</small></span></button>)}
            {!pending.has(active.id) && !cards[active.id] && <button onClick={() => void selectNode(active.id)}>Повторить загрузку</button>}
          </div>}
        </aside>}
        <div className="graph-hint">Колесо — масштаб · Перетаскивание — узел или карта · {Math.round(view.scale * 100)}%</div>
      </div>
    </section>
  );
}
