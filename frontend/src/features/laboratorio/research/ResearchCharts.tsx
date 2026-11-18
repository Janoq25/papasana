import type { ReactNode } from "react";
import { shortModel, type ResearchReport } from "./types";
export const INK = "#243528", GRID = "#dce4df";
export const COLORS = ["#176a72", "#a34d27", "#7051a2", "#526b24"];
export function SvgPaper({ title, subtitle, height = 530, note, children }: {
  title: string; subtitle?: string; height?: number; note?: string; children: ReactNode;
}) {
  const noteLines = note?.match(/.{1,110}(?:\s|$)/g)?.map((line) => line.trim()) ?? [];
  return <svg xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 900 ${height}`} role="img" aria-label={title} fontFamily="Arial, Helvetica, sans-serif" fontSize="17" fill={INK}>
    <title>{title}</title><rect width="900" height={height} fill="white" />
    <text x="34" y="37" fontSize="23" fontWeight="700">{title}</text>
    {subtitle && <text x="34" y="65" fontSize="16" fill="#4d5c50">{subtitle}</text>}
    {children}
    {noteLines.map((line, i) => <text key={i} x="34" y={height - 18 - (noteLines.length - 1 - i) * 19} fontSize="14" fill="#4d5c50">{line}</text>)}
  </svg>;
}
export function BarFigure({ title, subtitle, categories, series, max, unit = "", note }: {
  title: string; subtitle?: string; categories: string[]; series: { label: string; values: (number | null)[] }[];
  max?: number; unit?: string; note: string;
}) {
  const high = max ?? Math.max(1, ...series.flatMap((s) => s.values).filter((v): v is number => v != null && Number.isFinite(v))) * 1.2;
  const left = 80, top = 140, width = 790, height = 260;
  const group = width / categories.length;
  const bar = Math.min(80, (group - 35) / series.length);
  return <SvgPaper title={title} subtitle={subtitle} note={note}>
    {series.map((s, i) => <g key={s.label}><rect x={80 + i * 390} y="88" width="16" height="16" fill={COLORS[i]} /><text x={105 + i * 390} y="102" fontSize="16">{s.label}</text></g>)}
    {Array.from({ length: 5 }, (_, i) => {
      const value = high * i / 4, y = top + height * (1 - i / 4);
      return <g key={i}><line x1={left} y1={y} x2={left + width} y2={y} stroke={GRID} /><text x={left - 12} y={y + 6} textAnchor="end" fontSize="16">{high <= 1.2 ? value.toFixed(2) : Math.round(value)}</text></g>;
    })}
    <text x="20" y="275" transform="rotate(-90 20 275)" textAnchor="middle" fontSize="16">{unit || "F1 macro"}</text>
    {categories.map((c, i) => <g key={c}>
      {series.map((s, j) => {
        const value = s.values[i], h = value == null ? 0 : height * value / high;
        const x = left + group * (i + 0.5) + (j - series.length / 2) * bar;
        return <g key={s.label}><rect x={x} y={top + height - h} width={bar - 4} height={h} fill={COLORS[j]} />
          <text x={x + (bar - 4) / 2} y={top + height - h - 9} textAnchor="middle" fontSize="16">{value == null ? "N/D" : high <= 1.2 ? value.toFixed(4) : Number.isInteger(value) ? value : value.toFixed(1)}</text></g>;
      })}
      <text x={left + group * (i + 0.5)} y="429" textAnchor="middle" fontSize="16">{c.split("\n").map((line, k) => <tspan key={k} x={left + group * (i + 0.5)} dy={k ? 21 : 0}>{line}</tspan>)}</text>
    </g>)}
  </SvgPaper>;
}
export interface Series { label: string; points: { x: number; y: number }[] }
export function LineFigure({ title, subtitle, series, xLabel, yLabel, maxY, diagonal = false, note }: {
  title: string; subtitle?: string; series: Series[]; xLabel: string; yLabel: string; maxY?: number; diagonal?: boolean; note: string;
}) {
  const all = series.flatMap((s) => s.points).filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  const highX = diagonal ? 1 : Math.max(1, ...all.map((p) => p.x));
  const highY = maxY ?? Math.max(0.1, ...all.map((p) => p.y)) * 1.1;
  const x = (v: number) => 95 + v / highX * 750;
  const y = (v: number) => 420 - v / highY * 270;
  const dashes = [undefined, "10 4", "3 4", "10 4 3 4"];
  return <SvgPaper title={title} subtitle={subtitle} note={note}>
    {series.map((s, i) => <g key={s.label}><line x1={95 + i % 2 * 395} x2={126 + i % 2 * 395} y1={92 + Math.floor(i / 2) * 26} y2={92 + Math.floor(i / 2) * 26} stroke={COLORS[i % 4]} strokeWidth="3" strokeDasharray={dashes[i % 4]} /><text x={135 + i % 2 * 395} y={98 + Math.floor(i / 2) * 26} fontSize="16">{s.label}</text></g>)}
    {Array.from({ length: 6 }, (_, i) => <g key={i}>
      <line x1="95" x2="845" y1={y(highY * i / 5)} y2={y(highY * i / 5)} stroke={GRID} />
      <text x="82" y={y(highY * i / 5) + 5} textAnchor="end" fontSize="15">{(highY * i / 5).toFixed(2)}</text>
      <text x={x(highX * i / 5)} y="446" textAnchor="middle" fontSize="15">{highX <= 1.1 ? (highX * i / 5).toFixed(1) : Math.round(highX * i / 5)}</text>
    </g>)}
    <text x="470" y="478" textAnchor="middle" fontSize="17">{xLabel}</text>
    <text x="24" y="285" transform="rotate(-90 24 285)" textAnchor="middle" fontSize="17">{yLabel}</text>
    {diagonal && <path d={`M${x(0)},${y(0)} L${x(1)},${y(1)}`} fill="none" stroke="#87958b" strokeDasharray="5 5" />}
    {series.map((s, i) => <g key={s.label}>
      <path d={s.points.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)).map((p, k) => `${k ? "L" : "M"}${x(p.x)},${y(p.y)}`).join(" ")} fill="none" stroke={COLORS[i % 4]} strokeWidth="3" strokeDasharray={dashes[i % 4]} />
      {s.points.length <= 20 && s.points.map((p, k) => <circle key={k} cx={x(p.x)} cy={y(p.y)} r="3.5" fill={COLORS[i % 4]} />)}
    </g>)}
  </SvgPaper>;
}
export function MatrixFigure({ matrix, labels, title, subtitle, note }: { matrix: number[][]; labels: string[]; title: string; subtitle: string; note: string }) {
  const names: Record<string, string[]> = { sano: ["Sano"], sintomas_compatibles_tizon_tardio: ["Síntomas de", "tizón tardío"], otra_enfermedad_foliar: ["Otra enfermedad", "foliar"] };
  const high = Math.max(1, ...matrix.flat());
  return <SvgPaper title={title} subtitle={subtitle} height={650} note={note}>
    <text x="500" y="100" textAnchor="middle" fontWeight="700">Predicción</text>
    <text x="32" y="370" transform="rotate(-90 32 370)" textAnchor="middle" fontWeight="700">Referencia</text>
    {labels.map((label, i) => <g key={label}>
      <text x={330 + i * 130} y="130" textAnchor="middle" fontSize="16">{(names[label] ?? [label]).map((t, k) => <tspan key={k} x={330 + i * 130} dy={k ? 20 : 0}>{t}</tspan>)}</text>
      <text x="245" y={240 + i * 130} textAnchor="end" fontSize="17">{(names[label] ?? [label]).map((t, k) => <tspan key={k} x="245" dy={k ? 22 : 0}>{t}</tspan>)}</text>
    </g>)}
    {matrix.map((row, i) => row.map((count, j) => <g key={`${i}-${j}`}>
      <rect x={265 + j * 130} y={175 + i * 130} width="130" height="130" fill={`rgba(23,106,114,${0.08 + 0.86 * count / high})`} stroke="white" strokeWidth="3" />
      <text x={330 + j * 130} y={250 + i * 130} textAnchor="middle" fontSize="28" fontWeight="700" fill={count / high > 0.5 ? "white" : INK}>{count}</text>
    </g>))}
  </SvgPaper>;
}
function MethodBox({ x, y, width, title, lines, tone = "normal" }: { x: number; y: number; width: number; title: string; lines: string[]; tone?: "normal" | "external" }) {
  const height = 58 + lines.length * 23;
  return <g><rect x={x} y={y} width={width} height={height} rx="9" fill={tone === "external" ? "#fff7ed" : "#eff6f1"} stroke={tone === "external" ? "#a34d27" : "#578066"} strokeWidth="1.5" />
    <text x={x + width / 2} y={y + 30} textAnchor="middle" fontSize="20" fontWeight="700">{title}</text>
    {lines.map((line, i) => <text key={i} x={x + width / 2} y={y + 59 + 23 * i} textAnchor="middle" fontSize="17">{line}</text>)}
  </g>;
}
export function MethodologyFigure({ report }: { report: ResearchReport }) {
  const d = report.data;
  const sizes = [...new Set(report.models.map((m) => m.img_size))].join("/");
  const batches = [...new Set(report.models.map((m) => Number(m.train.batch_size) * Number(m.train.accumulation_steps)))].join("/");
  const epochs = [...new Set(report.models.map((m) => m.train.epochs))].join("/");
  const precision = [...new Set(report.models.map((m) => !m.train.amp ? "FP32" : m.train.amp_dtype === "bfloat16" ? "BF16" : "FP16"))].join(" / ");
  const externalF1 = report.models.map((m) => m.evaluation.external_plantdoc_papa?.macro_f1).filter((v): v is number => v != null);
  const arrow = (path: string, dashed = false) => <path d={path} fill="none" stroke="#578066" strokeWidth="2" strokeDasharray={dashed ? "7 5" : undefined} markerEnd="url(#methodology-arrow)" />;
  return <SvgPaper title="PapaSana · metodología ejecutada" subtitle="Preparación y EDA → desarrollo agrupado → evaluación → artefactos" height={1260} note="Piloto con holdout agrupado. Validación anidada y evaluación prospectiva: pendientes.">
    <defs><marker id="methodology-arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 Z" fill="#578066" /></marker></defs>
    <MethodBox x={50} y={90} width={800} title="1. Fuentes y licencias verificadas" lines={[`PlantVillage + PlantDoc · ${d.original} imágenes de papa`, "Revisiones de origen fijadas y trazabilidad SHA-256"]} />
    {arrow("M450,194 L450,220")}
    <MethodBox x={50} y={220} width={800} title="2. Preparación y control de calidad" lines={[`Deduplicación exacta/perceptual: ${d.duplicates_removed} copias exactas retiradas`, `Conflictos de etiquetas: ${d.quarantined} imágenes en cuarentena`]} />
    {arrow("M450,324 L450,350")}
    <MethodBox x={50} y={350} width={800} title="3. EDA del conjunto utilizable" lines={[`${d.accepted} imágenes · distribución de clases, fuentes y particiones`]} />
    {arrow("M450,431 L450,448 L230,448 L230,475")}{arrow("M450,448 L670,448 L670,475")}
    <MethodBox x={30} y={475} width={400} title="PlantVillage · desarrollo" lines={[`${d.train + d.validation} imágenes · ${d.leaf_groups} hojas agrupadas`, "Tres clases por síntomas"]} />
    <MethodBox x={470} y={475} width={400} title="PlantDoc · externo" lines={[`${d.external} imágenes · sin hojas sanas`, "Ya observado: uso descriptivo"]} tone="external" />
    {arrow("M230,579 L230,615")}
    <MethodBox x={30} y={615} width={400} title="4. Partición sin fuga de hojas" lines={[`${d.train} entrenamiento / ${d.validation} validación`, `${d.folds.length} folds preparados; holdout = fold ${d.validation_fold}`]} />
    {arrow("M230,719 L230,755")}
    <MethodBox x={30} y={755} width={400} title={`5. Ajuste de ${report.models.length} modelos`} lines={[report.models.slice(0, 2).map((m) => shortModel[m.architecture] ?? m.label).join(" · "), report.models.slice(2).map((m) => shortModel[m.architecture] ?? m.label).join(" · "), `${sizes} px · AdamW · CUDA · lote nominal ${batches}`, `Hasta ${epochs} épocas · parada · ${precision}`]} />
    {arrow("M230,905 L230,950")}
    <MethodBox x={30} y={950} width={400} title="6. Selección y calibración" lines={["Mejor checkpoint y temperatura en validación", "Arquitectura: F1 interno y tiempo", "PlantDoc fuera de la selección"]} />
    {arrow("M670,579 L670,950", true)}
    <text x="688" y="735" fontSize="16" fill="#87512a">Sin ajuste ni selección</text>
    {arrow("M430,1013 L470,1013")}
    <MethodBox x={470} y={950} width={400} title="7. Evaluación descriptiva" lines={[`${d.external} imágenes · dos clases presentes`, `F1 externo: ${Math.min(...externalF1).toFixed(3)}–${Math.max(...externalF1).toFixed(3)}`, "Limitaciones de dominio documentadas"]} tone="external" />
    {arrow("M670,1077 L670,1091 L450,1091 L450,1105")}
    <MethodBox x={50} y={1105} width={800} title="8. Verificación y resultados para el artículo" lines={["Recarga de checkpoints y Grad-CAM · métricas, curvas y matrices", "Figuras a 600 DPI · tablas editables · identificadores de ejecución"]} />
  </SvgPaper>;
}
