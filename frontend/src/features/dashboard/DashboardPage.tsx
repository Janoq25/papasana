import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControlLabel,
  Grid,
  LinearProgress,
  MenuItem,
  Paper,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import { api } from "../../api/client";
import type { DashboardData, ReportOptions } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import ErrorAlert from "../../components/ErrorAlert";
import HeatMap from "../../components/HeatMap";
import PageHeader from "../../components/PageHeader";
import ExportReportDialog from "../reportes/ExportReportDialog";
import { CategoryDonut, StackedBars, TrendChart } from "./charts";
import { type DashboardFilters, defaultFilters, filtersFromParams, filtersToParams, rangeError } from "./filters";
import KpiGrid from "./KpiGrid";

const SCOPE_TEXT: Record<DashboardData["alcance"], string> = {
  todo: "Mostrando todos los datos del sistema.",
  region: "Mostrando los datos de su región.",
  propio: "Mostrando solo sus parcelas y sus diagnósticos.",
};

function Section({ title, children, subtitle }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
      <Typography variant="h3" component="h2">{title}</Typography>
      {subtitle && <Typography variant="caption" color="text.secondary">{subtitle}</Typography>}
      <Box sx={{ mt: 1 }}>{children}</Box>
    </Paper>
  );
}

function FiltersBar({ filters, options, onChange, onReset }: {
  filters: DashboardFilters;
  options?: Pick<ReportOptions, "regions" | "parcels" | "varieties">;
  onChange(f: DashboardFilters): void;
  onReset(): void;
}) {
  const set = (k: keyof DashboardFilters) => (e: React.ChangeEvent<HTMLInputElement>) => onChange({ ...filters, [k]: e.target.value });
  const error = rangeError(filters);
  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }} component="section" aria-label="Filtros globales">
      <Grid container spacing={2} sx={{ alignItems: "center" }}>
        <Grid size={{ xs: 6, md: 2 }}>
          <TextField label="Desde" type="date" value={filters.date_from} onChange={set("date_from")}
            slotProps={{ inputLabel: { shrink: true } }} />
        </Grid>
        <Grid size={{ xs: 6, md: 2 }}>
          <TextField label="Hasta" type="date" value={filters.date_to} onChange={set("date_to")} error={!!error}
            helperText={error ?? undefined} slotProps={{ inputLabel: { shrink: true } }} />
        </Grid>
        <Grid size={{ xs: 12, sm: 4, md: 2.5 }}>
          <TextField select label="Región" value={filters.region_code} onChange={set("region_code")}>
            <MenuItem value="">Todas</MenuItem>
            {options?.regions.map((r) => <MenuItem key={r.code} value={r.code}>{r.name}</MenuItem>)}
          </TextField>
        </Grid>
        <Grid size={{ xs: 12, sm: 4, md: 2.5 }}>
          <TextField select label="Parcela" value={filters.parcel_id} onChange={set("parcel_id")}>
            <MenuItem value="">Todas</MenuItem>
            {options?.parcels.map((p) => <MenuItem key={p.id} value={String(p.id)}>{p.code} · {p.name}</MenuItem>)}
          </TextField>
        </Grid>
        <Grid size={{ xs: 12, sm: 4, md: 2 }}>
          <TextField select label="Variedad" value={filters.variety_id} onChange={set("variety_id")}>
            <MenuItem value="">Todas</MenuItem>
            {options?.varieties.map((v) => <MenuItem key={v.id} value={String(v.id)}>{v.name}</MenuItem>)}
          </TextField>
        </Grid>
        <Grid size={{ xs: 12, md: 1 }}>
          <Button onClick={onReset} fullWidth>Restablecer</Button>
        </Grid>
      </Grid>
    </Paper>
  );
}

export default function DashboardPage() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const defaults = useMemo(() => defaultFilters(), []);
  const filters = filtersFromParams(params, defaults);
  const invalid = !!rangeError(filters);
  const [includeHealthy, setIncludeHealthy] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  const options = useQuery({
    queryKey: ["dashboard", "opciones"],
    queryFn: () => api<Pick<ReportOptions, "regions" | "parcels" | "varieties">>("/dashboard/opciones"),
    staleTime: 120_000,
  });
  const q = useQuery({
    queryKey: ["dashboard", filters],
    queryFn: () => api<DashboardData>("/dashboard", { query: { ...filters } }),
    enabled: !invalid,
    placeholderData: keepPreviousData,
  });
  const d = q.data;
  const points = useMemo(
    () => (d?.mapa ?? []).filter((p) => includeHealthy || p.categoria !== "sano"),
    [d, includeHealthy],
  );
  const approximate = points.filter((p) => p.aproximado).length;
  const canExport = can("dashboard:exportar") && can("reportes:exportar");

  return (
    <Box>
      <PageHeader title="Dashboard" subtitle={d ? SCOPE_TEXT[d.alcance] : "Indicadores de diagnóstico y distribución de casos."}
        actions={canExport && (
          <Button variant="outlined" startIcon={<FileDownloadIcon />} onClick={() => setExportOpen(true)}>Exportar</Button>
        )} />
      <FiltersBar filters={filters} options={options.data}
        onChange={(f) => setParams(filtersToParams(f, defaults), { replace: true })}
        onReset={() => setParams({}, { replace: true })} />
      {q.isFetching && <LinearProgress sx={{ mb: 1 }} aria-label="Actualizando el dashboard" />}
      <ErrorAlert error={q.error ?? options.error} />

      {d?.modelo?.is_demo && (
        <Alert severity="error" variant="filled" sx={{ mb: 2 }}>
          <strong>DEMO / no validado.</strong> Los diagnósticos provienen de un modelo de demostración sin entrenar: las
          cifras sirven para probar el sistema, no describen la situación sanitaria de las parcelas.
        </Alert>
      )}
      {!!d?.kpis.diagnosticos_ejemplo && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Incluye {d.kpis.diagnosticos_ejemplo} diagnósticos <strong>de ejemplo</strong> generados con imágenes sintéticas
          para demostrar el dashboard (procedencia "Datos de ejemplo").
        </Alert>
      )}

      {d && (
        <>
          <Box sx={{ mb: 2 }}><KpiGrid kpis={d.kpis} canValidate={can("validacion:ver")} /></Box>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, lg: 8 }}>
              <Section title="Tendencia de diagnósticos"
                subtitle={`Agregación ${d.tendencia.granularidad === "dia" ? "diaria" : d.tendencia.granularidad === "semana" ? "semanal (semanas que inician el lunes)" : "mensual"}`}>
                <TrendChart trend={d.tendencia} />
              </Section>
            </Grid>
            <Grid size={{ xs: 12, lg: 4 }}>
              <Section title="Distribución por categoría"><CategoryDonut kpis={d.kpis} /></Section>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Section title="Por región" subtitle="Departamento de la parcela">
                <StackedBars rows={d.por_region} label="Diagnósticos por región" />
              </Section>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Section title="Por variedad"><StackedBars rows={d.por_variedad} label="Diagnósticos por variedad" /></Section>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <Section title="Mapa de calor de casos"
                subtitle="Ubicación de cada fotografía; si no tiene GPS, se usa el centro de la parcela.">
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center", mb: 1 }}>
                  <FormControlLabel label="Incluir diagnósticos sanos"
                    control={<Switch checked={includeHealthy} onChange={(e) => setIncludeHealthy(e.target.checked)} />} />
                  <Chip size="small" label={`${points.length} casos en el mapa`} />
                  {approximate > 0 && <Chip size="small" variant="outlined" label={`${approximate} con ubicación aproximada`} />}
                  {d.mapa_truncado && <Chip size="small" color="warning" label="Se muestran los 5 000 más recientes" />}
                </Box>
                <HeatMap points={points} />
              </Section>
            </Grid>
          </Grid>
        </>
      )}
      <ExportReportDialog open={exportOpen} onClose={() => setExportOpen(false)} codes={["R-07", "R-06", "R-01"]}
        filters={{ ...filters }} title="Exportar los datos del dashboard" />
    </Box>
  );
}
