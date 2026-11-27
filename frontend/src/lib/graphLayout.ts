import type { KnowledgeGraph } from "../types";

export type GraphNode = {
  id: string; name: string; summary: string; kind: "domain" | "concept";
  count: number; x: number; y: number;
};
export type Link = { source: string; target: string; domain: boolean };
export type GraphLayout = { nodes: GraphNode[]; links: Link[] };

export function createLayout(graph: KnowledgeGraph): GraphLayout {
  const nodes: GraphNode[] = [
    ...graph.domains.map((d) => ({ ...d, kind: "domain" as const, count: 0 })),
    ...graph.concepts.map((c) => ({ ...c, kind: "concept" as const, count: c.card_count })),
  ].map((node, i) => {
    const angle = i * 2.399963229728653, radius = 36 * Math.sqrt(i + 1);
    return { ...node, x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
  });
  const ids = new Set(nodes.map((n) => n.id));
  const links = [
    ...graph.edges.map((e) => ({ source: e.source_id, target: e.target_id, domain: false })),
    ...graph.concepts.map((c) => ({ source: c.domain_id, target: c.id, domain: true })),
  ].filter((e) => e.source !== e.target && ids.has(e.source) && ids.has(e.target));
  return { nodes, links };
}

// Spatial buckets bound repulsion work; run in animation-frame batches.
export function relaxLayout(layout: GraphLayout, cooling: number) {
  const cells = new Map<string, GraphNode[]>();
  const forces = new Map(layout.nodes.map((n) => [n.id, { x: -n.x * 0.001, y: -n.y * 0.001 }]));
  const nodes = new Map(layout.nodes.map((n) => [n.id, n]));
  const cellSize = 160;
  for (const node of layout.nodes) {
    const key = Math.floor(node.x / cellSize) + "," + Math.floor(node.y / cellSize);
    const cell = cells.get(key) ?? [];
    cell.push(node); cells.set(key, cell);
  }
  for (const node of layout.nodes) {
    const force = forces.get(node.id)!;
    const cx = Math.floor(node.x / cellSize), cy = Math.floor(node.y / cellSize);
    for (let x = cx - 1; x <= cx + 1; x++) {
      for (let y = cy - 1; y <= cy + 1; y++) {
        for (const other of cells.get(x + "," + y) ?? []) {
          if (node.id === other.id) continue;
          const dx = node.x - other.x, dy = node.y - other.y;
          const distance = Math.max(1, Math.hypot(dx, dy));
          const strength = 1100 / (distance * distance);
          force.x += dx / distance * strength; force.y += dy / distance * strength;
        }
      }
    }
  }
  for (const link of layout.links) {
    const a = nodes.get(link.source)!, b = nodes.get(link.target)!;
    const dx = b.x - a.x, dy = b.y - a.y;
    const distance = Math.max(1, Math.hypot(dx, dy));
    const strength = (distance - (link.domain ? 100 : 130)) * 0.025;
    const fx = dx / distance * strength, fy = dy / distance * strength;
    forces.get(a.id)!.x += fx; forces.get(a.id)!.y += fy;
    forces.get(b.id)!.x -= fx; forces.get(b.id)!.y -= fy;
  }
  for (const node of layout.nodes) {
    const force = forces.get(node.id)!;
    node.x += Math.max(-12, Math.min(12, force.x)) * cooling;
    node.y += Math.max(-12, Math.min(12, force.y)) * cooling;
  }
}
