import { useEffect, useMemo, useRef, useState } from "react";
import { geoNaturalEarth1, geoPath, type GeoProjection } from "d3-geo";
import { select } from "d3-selection";
import { zoom as d3zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
import { feature } from "topojson-client";
import { Crosshair, Minus, Pause, Play, Plus } from "lucide-react";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import worldTopo from "../assets/world-110m.json";
import type { MapConnection, MapNode } from "../lib/types";
import { NODE_COLOR } from "../lib/constants";
import { formatMs, formatNumber, formatPercent } from "../lib/format";

// Decode the bundled world geography once.
const WORLD = feature(
  worldTopo as unknown as Parameters<typeof feature>[0],
  (worldTopo as any).objects.countries
) as unknown as FeatureCollection<Geometry>;

interface Props {
  nodes: MapNode[];
  connections: MapConnection[];
  animate: boolean;
  onToggleAnimate: () => void;
  height?: number;
  onSelectNode?: (node: MapNode | null) => void;
}

export function NetworkMap({
  nodes,
  connections,
  animate,
  onToggleAnimate,
  height = 520,
  onSelectNode,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const gRef = useRef<SVGGElement>(null);
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [width, setWidth] = useState(900);
  const [k, setK] = useState(1);
  const [selected, setSelected] = useState<MapNode | null>(null);

  // Respect reduced-motion for particle animation.
  const prefersReducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const particlesOn = animate && !prefersReducedMotion;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width;
      if (w > 0) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const projection: GeoProjection = useMemo(() => {
    const proj = geoNaturalEarth1();
    proj.fitExtent(
      [
        [8, 8],
        [width - 8, height - 8],
      ],
      WORLD as unknown as Feature
    );
    return proj;
  }, [width, height]);

  const pathGen = useMemo(() => geoPath(projection), [projection]);

  const project = (lon: number, lat: number): [number, number] | null => {
    const p = projection([lon, lat]);
    return p ? [p[0], p[1]] : null;
  };

  // Set up zoom/pan behaviour.
  useEffect(() => {
    if (!svgRef.current || !gRef.current) return;
    const svg = select(svgRef.current);
    const g = select(gRef.current);
    const zoomBehavior = d3zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .translateExtent([
        [0, 0],
        [width, height],
      ])
      .on("zoom", (event) => {
        g.attr("transform", event.transform.toString());
        setK(event.transform.k);
      });
    zoomRef.current = zoomBehavior;
    svg.call(zoomBehavior);
    svg.on("dblclick.zoom", null);
    return () => {
      svg.on(".zoom", null);
    };
  }, [width, height]);

  const doZoom = (factor: number) => {
    if (!svgRef.current || !zoomRef.current) return;
    zoomRef.current.scaleBy(select(svgRef.current), factor);
  };
  const resetZoom = () => {
    if (!svgRef.current || !zoomRef.current) return;
    zoomRef.current.transform(select(svgRef.current), zoomIdentity);
    pick(null);
  };

  const pick = (n: MapNode | null) => {
    setSelected(n);
    onSelectNode?.(n);
  };

  // Precompute connection arc paths (quadratic bezier with a lifted control pt).
  const arcs = useMemo(() => {
    return connections
      .map((c) => {
        const a = project(c.src.lon, c.src.lat);
        const b = project(c.dst.lon, c.dst.lat);
        if (!a || !b) return null;
        const mx = (a[0] + b[0]) / 2;
        const my = (a[1] + b[1]) / 2;
        const dx = b[0] - a[0];
        const dy = b[1] - a[1];
        const dist = Math.hypot(dx, dy);
        // Perpendicular lift proportional to distance for a pleasing arc.
        const lift = Math.min(dist * 0.22, 80);
        const nx = -dy / (dist || 1);
        const ny = dx / (dist || 1);
        const cx = mx + nx * lift;
        const cy = my + ny * lift;
        const d = `M${a[0]},${a[1]} Q${cx},${cy} ${b[0]},${b[1]}`;
        return { id: c.id, d, suspicious: c.suspicious };
      })
      .filter(Boolean) as { id: number; d: string; suspicious: boolean }[];
  }, [connections, projection]);

  const nodeR = (n: MapNode) => {
    const base = n.color === "red" ? 6 : n.color === "blue" ? 5.5 : 4.5;
    return base / k; // counter-scale so nodes stay readable when zoomed
  };

  return (
    <div className="relative" ref={containerRef}>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="block touch-none rounded-lg"
        style={{ background: "radial-gradient(ellipse at 50% 35%, #0b1a2e 0%, #050a12 70%)" }}
      >
        <defs>
          <filter id="nodeGlow" x="-120%" y="-120%" width="340%" height="340%">
            <feGaussianBlur stdDeviation="2.4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g ref={gRef}>
          {/* Graticule-free world land */}
          {(WORLD.features as Feature<Geometry>[]).map((f, i) => (
            <path
              key={i}
              d={pathGen(f) ?? undefined}
              fill="#0e2136"
              stroke="#1D3349"
              strokeWidth={0.5}
              vectorEffect="non-scaling-stroke"
            />
          ))}

          {/* Connection arcs */}
          {arcs.map((arc) => (
            <g key={arc.id}>
              <path id={`arc-${arc.id}`} d={arc.d} fill="none" />
              <use
                href={`#arc-${arc.id}`}
                stroke={arc.suspicious ? "#FF5268" : "#13D6C1"}
                strokeWidth={arc.suspicious ? 1.3 : 0.9}
                strokeOpacity={arc.suspicious ? 0.9 : 0.45}
                strokeDasharray={arc.suspicious ? "4 3" : undefined}
                fill="none"
                vectorEffect="non-scaling-stroke"
              />
              {particlesOn && (
                <circle r={arc.suspicious ? 1.6 : 1.3} fill={arc.suspicious ? "#FF8A8A" : "#20D9F2"}>
                  <animateMotion
                    dur={`${arc.suspicious ? 2.2 : 3.4}s`}
                    repeatCount="indefinite"
                    keyPoints="0;1"
                    keyTimes="0;1"
                    calcMode="linear"
                  >
                    <mpath href={`#arc-${arc.id}`} />
                  </animateMotion>
                </circle>
              )}
            </g>
          ))}

          {/* Nodes */}
          {nodes.map((n) => {
            const p = project(n.lon, n.lat);
            if (!p) return null;
            const color = NODE_COLOR[n.color] ?? "#20D9F2";
            const isSel = selected?.id === n.id;
            return (
              <g
                key={n.id}
                transform={`translate(${p[0]},${p[1]})`}
                className="cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  pick(isSel ? null : n);
                }}
              >
                {/* soft halo */}
                <circle r={nodeR(n) * 2.6} fill={color} opacity={0.12} />
                {(n.color === "red" || n.color === "amber") && (
                  <circle
                    r={nodeR(n) * 2.6}
                    fill="none"
                    stroke={color}
                    strokeWidth={0.8 / k}
                    className={particlesOn ? "animate-pulseGlow" : ""}
                  />
                )}
                <circle r={nodeR(n)} fill={color} filter="url(#nodeGlow)" />
                {isSel && (
                  <circle r={nodeR(n) * 3.4} fill="none" stroke="#ECF5FF" strokeWidth={1 / k} />
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Zoom controls */}
      <div className="absolute left-3 top-3 flex flex-col gap-1">
        <button className="btn px-2 py-1" onClick={() => doZoom(1.5)} aria-label="Zoom in">
          <Plus className="h-4 w-4" />
        </button>
        <button className="btn px-2 py-1" onClick={() => doZoom(1 / 1.5)} aria-label="Zoom out">
          <Minus className="h-4 w-4" />
        </button>
        <button className="btn px-2 py-1" onClick={resetZoom} aria-label="Reset view">
          <Crosshair className="h-4 w-4" />
        </button>
      </div>

      {/* Animation toggle */}
      <button
        className="btn absolute right-3 top-3 px-2 py-1"
        onClick={onToggleAnimate}
        aria-label={animate ? "Pause animation" : "Play animation"}
      >
        {animate ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
      </button>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 rounded-lg border border-border bg-card/90 px-3 py-2 text-[11px] text-muted backdrop-blur">
        <div className="mb-1 flex flex-wrap gap-x-4 gap-y-1">
          <Legend color="#20D9F2" label="Normal node" />
          <Legend color="#338BFF" label="High traffic" />
          <Legend color="#FFBF47" label="Anomaly" />
          <Legend color="#FF5268" label="Alert" />
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <LegendLine color="#13D6C1" dashed={false} label="Connection" />
          <LegendLine color="#FF5268" dashed label="Suspicious" />
        </div>
      </div>

      {/* Selected node detail */}
      {selected && (
        <div className="absolute bottom-3 right-3 w-60 rounded-lg border border-border bg-card/95 p-3 text-sm backdrop-blur animate-fadeIn">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-text">{selected.name}</span>
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: NODE_COLOR[selected.color] }}
            />
          </div>
          <div className="mt-1 text-xs text-muted">
            {[selected.city, selected.country].filter(Boolean).join(", ") || "Location unknown"}
          </div>
          <dl className="mt-2 space-y-1 text-xs">
            <Row label="Request rate" value={`${formatNumber(selected.request_rate)} /s`} />
            <Row label="Error rate" value={formatPercent(selected.error_rate)} />
            <Row label="Latency p95" value={formatMs(selected.latency_p95_ms)} />
            <Row
              label="Status"
              value={selected.available === false ? "Unavailable" : "Available"}
            />
          </dl>
          {selected.is_demo && (
            <div className="mt-2 text-[10px] uppercase tracking-wider text-warning">Demo data</div>
          )}
        </div>
      )}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
function LegendLine({ color, dashed, label }: { color: string; dashed: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <svg width="18" height="6">
        <line
          x1="0"
          y1="3"
          x2="18"
          y2="3"
          stroke={color}
          strokeWidth="1.5"
          strokeDasharray={dashed ? "3 2" : undefined}
        />
      </svg>
      {label}
    </span>
  );
}
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-muted">{label}</dt>
      <dd className="font-mono text-text">{value}</dd>
    </div>
  );
}
