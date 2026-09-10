import { describe, expect, it } from "vitest";
import { layout } from "./graph-layout";

describe("graph layout", () => {
  it("keeps long serial plans readable without changing runtime relationships", () => {
    const nodes = Array.from({ length: 9 }, (_, i) => ({
      id: String(i),
      data: { label: String(i) },
      position: { x: 0, y: 0 },
    }));
    const edges = nodes
      .slice(1)
      .map((n, i) => ({ id: n.id, source: String(i), target: n.id }));
    const before = JSON.stringify({ nodes, edges });
    const result = layout(nodes, edges);
    expect(JSON.stringify({ nodes, edges })).toBe(before);
    expect(result.map((n) => n.id)).toEqual(nodes.map((n) => n.id));
    expect(new Set(result.map((n) => JSON.stringify(n.position))).size).toBe(9);
    expect(
      Math.max(...result.map((n) => n.position.x)) + 240,
    ).toBeLessThanOrEqual(1200);
    expect(
      Math.max(...result.map((n) => n.position.y)) + 100,
    ).toBeLessThanOrEqual(600);
    expect(result[3].position.y).toBeLessThan(result[4].position.y);
    expect(result[4].position.x).toBeGreaterThan(result[5].position.x);
  });
  it("retains layered dependency order for branching plans and handles an empty plan", () => {
    const nodes = ["root", "a", "b", "end"].map((id) => ({
      id,
      data: {},
      position: { x: 0, y: 0 },
    }));
    const links = [
      ["root", "a"],
      ["root", "b"],
      ["a", "end"],
      ["b", "end"],
    ];
    const result = new Map(
      layout(
        nodes,
        links.map(([source, target]) => ({
          id: source + target,
          source,
          target,
        })),
      ).map((n) => [n.id, n.position]),
    );
    for (const [source, target] of links)
      expect(result.get(source)!.x).toBeLessThan(result.get(target)!.x);
    expect(result.get("a")!.y).not.toBe(result.get("b")!.y);
    expect(layout([], [])).toEqual([]);
  });
});
