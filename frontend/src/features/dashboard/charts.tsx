import { Box, Typography } from "@mui/material";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CategoryCounts, DashboardData } from "../../api/types";
import { CATEGORY_LABEL } from "../../utils/diagnosis";
import { periodLabel } from "./filters";

/** Colores con contraste ≥ 3:1 sobre blanco (elementos gráficos, WCAG 1.4.11). */
export const CATEGORY_HEX: Record<keyof CategoryCounts, string> = {
  sano: "#2e6b30",
  sospechoso: "#b07000",
  tizon_tardio_compatible: "#b3261e",
};
const ORDER: (keyof CategoryCounts)[] = ["tizon_tardio_compatible", "sospechoso", "sano"];
const SHORT: Record<keyof CategoryCounts, string> = {
  sano: "Sano",
  sospechoso: "Sospechoso",
  tizon_tardio_compatible: "Compatible con tizón",
};

function Empty() {
  return (
    <Box sx={{ height: "100%", display: "grid", placeItems: "center" }}>
      <Typography color="text.secondary">Sin diagnósticos para los filtros seleccionados.</Typography>
    </Box>
  );
}

function summary(rows: ({ total?: number } & CategoryCounts)[]): string {
  const t = rows.reduce((acc, r) => ({
    sano: acc.sano + r.sano, sospechoso: acc.sospechoso + r.sospechoso,
    tizon_tardio_compatible: acc.tizon_tardio_compatible + r.tizon_tardio_compatible,
  }), { sano: 0, sospechoso: 0, tizon_tardio_compatible: 0 });
  return ORDER.map((k) => `${CATEGORY_LABEL[k]}: ${t[k]}`).join("; ");
}

export function TrendChart({ trend }: { trend: DashboardData["tendencia"] }) {
  const data = trend.series.map((p) => ({ ...p, label: periodLabel(p.periodo, trend.granularidad) }));
  const total = data.reduce((n, p) => n + p.sano + p.sospechoso + p.tizon_tardio_compatible, 0);
  return (
    <Box sx={{ height: 300 }} role="img"
      aria-label={`Tendencia ${trend.granularidad === "dia" ? "diaria" : trend.granularidad === "semana" ? "semanal" : "mensual"} de diagnósticos. ${summary(trend.series)}`}>
      {total === 0 ? <Empty /> : (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} interval="preserveStartEnd" minTickGap={12} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {ORDER.map((k) => (
              <Bar key={k} dataKey={k} name={SHORT[k]} stackId="c" fill={CATEGORY_HEX[k]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </Box>
  );
}

export function CategoryDonut({ kpis }: { kpis: DashboardData["kpis"] }) {
  const data = kpis.por_categoria.filter((c) => c.total > 0).map((c) => ({ name: SHORT[c.categoria], value: c.total, key: c.categoria }));
  return (
    <Box sx={{ height: 300 }} role="img"
      aria-label={`Distribución por categoría. ${kpis.por_categoria.map((c) => `${c.etiqueta}: ${c.total}`).join("; ")}`}>
      {data.length === 0 ? <Empty /> : (
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius="50%" outerRadius="80%" paddingAngle={2}
              label={({ percent: p }) => `${((p ?? 0) * 100).toFixed(0)} %`}>
              {data.map((d) => <Cell key={d.key} fill={CATEGORY_HEX[d.key]} />)}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )}
    </Box>
  );
}

export function StackedBars({ rows, label }: { rows: ({ nombre: string } & CategoryCounts)[]; label: string }) {
  const height = Math.max(160, 48 + rows.length * 34);
  return (
    <Box sx={{ height }} role="img" aria-label={`${label}. ${rows.map((r) => `${r.nombre}: ${r.sano + r.sospechoso + r.tizon_tardio_compatible}`).join("; ")}`}>
      {rows.length === 0 ? <Empty /> : (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 12, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
            <YAxis type="category" dataKey="nombre" width={110} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {ORDER.map((k) => (
              <Bar key={k} dataKey={k} name={SHORT[k]} stackId="c" fill={CATEGORY_HEX[k]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </Box>
  );
}
