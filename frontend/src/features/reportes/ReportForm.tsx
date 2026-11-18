import { useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, Grid, MenuItem, TextField, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import type { ReportDefinition, ReportFilterField, ReportFormat, ReportOptions } from "../../api/types";
import { cleanFilters, FORMAT_LABELS } from "./useReports";

interface Props {
  definition: ReportDefinition;
  options?: ReportOptions;
  initial?: Record<string, string>;
  busy?: boolean;
  onSubmit(format: ReportFormat, filters: Record<string, string | number>): void;
}

function choices(field: ReportFilterField, options?: ReportOptions): [string, string][] {
  switch (field.type) {
    case "select":
      return Object.entries(field.options ?? {});
    case "region":
      return (options?.regions ?? []).map((r) => [r.code, r.name]);
    case "parcel":
      return (options?.parcels ?? []).map((p) => [String(p.id), `${p.code} · ${p.name}`]);
    case "variety":
      return (options?.varieties ?? []).map((v) => [String(v.id), v.name]);
    case "technician":
      return (options?.technicians ?? []).map((t) => [t.id, t.name]);
    case "model":
      return (options?.model_versions ?? []).map((m) => [String(m.id), m.is_demo ? `${m.name} (DEMO)` : m.name]);
    case "role":
      return (options?.roles ?? []).map((r) => [r.code, r.name]);
    case "module":
      return (options?.modules ?? []).map((m) => [m.code, m.name]);
    default:
      return [];
  }
}

export function FilterField({ field, value, options, error, onChange }: {
  field: ReportFilterField;
  value: string;
  options?: ReportOptions;
  error?: string;
  onChange(v: string): void;
}) {
  const id = `filtro-${field.key}`;
  if (field.type === "date") {
    return (
      <TextField id={id} label={field.label} type="date" value={value} onChange={(e) => onChange(e.target.value)}
        error={!!error} helperText={error} slotProps={{ inputLabel: { shrink: true } }} />
    );
  }
  if (field.type === "number") {
    return (
      <TextField id={id} label={field.label} type="number" value={value} onChange={(e) => onChange(e.target.value)}
        slotProps={{ htmlInput: { min: 0, max: 3650 } }} />
    );
  }
  if (field.type === "text") {
    return <TextField id={id} label={field.label} value={value} onChange={(e) => onChange(e.target.value)} />;
  }
  return (
    <TextField id={id} select label={field.label} value={value} onChange={(e) => onChange(e.target.value)}>
      <MenuItem value="">Todos</MenuItem>
      {choices(field, options).map(([k, v]) => (
        <MenuItem key={k} value={k}>{v}</MenuItem>
      ))}
    </TextField>
  );
}

export default function ReportForm({ definition, options, initial, busy, onSubmit }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const keys = useMemo(() => definition.filters.map((f) => f.key), [definition]);

  useEffect(() => {
    const start: Record<string, string> = {};
    keys.forEach((k) => {
      if (initial?.[k]) start[k] = initial[k];
    });
    setValues(start);
  }, [keys, initial]);

  const dateError =
    values.date_from && values.date_to && values.date_from > values.date_to
      ? "Debe ser igual o posterior a la fecha inicial"
      : undefined;

  return (
    <Box component="form" noValidate aria-label={`Filtros del reporte ${definition.code}`}
      onSubmit={(e) => {
        e.preventDefault();
        if (!dateError) onSubmit(format, cleanFilters(values, keys));
      }}>
      {definition.available_from_phase && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Este reporte depende de un módulo de la Fase {definition.available_from_phase}. Ya se genera con su formato
          definitivo, pero por ahora no tendrá registros.
        </Alert>
      )}
      <Grid container spacing={2}>
        {definition.filters.map((f) => (
          <Grid key={f.key} size={{ xs: 12, sm: 6, md: 4 }}>
            <FilterField field={f} value={values[f.key] ?? ""} options={options}
              error={f.key === "date_to" ? dateError : undefined}
              onChange={(v) => setValues((cur) => ({ ...cur, [f.key]: v }))} />
          </Grid>
        ))}
      </Grid>
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 2, mt: 3 }}>
        <Box>
          <Typography variant="caption" color="text.secondary" component="div" id="formato-label">Formato</Typography>
          <ToggleButtonGroup exclusive size="small" value={format} aria-labelledby="formato-label"
            onChange={(_, v: ReportFormat | null) => v && setFormat(v)}>
            {definition.formats.map((f) => (
              <ToggleButton key={f} value={f} aria-label={FORMAT_LABELS[f]}>{FORMAT_LABELS[f]}</ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Box>
        <Box sx={{ flexGrow: 1 }} />
        <Button type="button" onClick={() => setValues({})} disabled={busy}>Limpiar filtros</Button>
        <Button type="submit" variant="contained" disabled={busy || !!dateError}>
          {busy ? "Enviando…" : "Generar reporte"}
        </Button>
      </Box>
    </Box>
  );
}
