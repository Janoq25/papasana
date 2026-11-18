import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Chip,
  Grid,
  List,
  ListItemButton,
  ListItemText,
  ListSubheader,
  Paper,
  Typography,
} from "@mui/material";
import { useAuth } from "../../auth/AuthContext";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import type { ReportDefinition } from "../../api/types";
import ReportForm from "./ReportForm";
import ReportHistory from "./ReportHistory";
import { FORMAT_LABELS, useReportCatalog, useReportOptions, useRequestReport } from "./useReports";

const KIND_ORDER: ReportDefinition["kind"][] = ["operacional", "gestion", "auditoria"];
const KIND_TITLES: Record<ReportDefinition["kind"], string> = {
  operacional: "Operacionales",
  gestion: "De gestión",
  auditoria: "Auditoría",
};

export default function ReportsPage() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const catalog = useReportCatalog();
  const options = useReportOptions();
  const request = useRequestReport();
  const [sentMessage, setSentMessage] = useState<string | null>(null);
  const canExport = can("reportes:exportar") || can("bitacora:exportar");

  const defs = catalog.data ?? [];
  const selected = defs.find((d) => d.code === params.get("reporte")) ?? defs[0];
  // Filtros que llegan en la URL (por ejemplo, desde el dashboard)
  const initial = useMemo(() => {
    const out: Record<string, string> = {};
    params.forEach((v, k) => {
      if (k !== "reporte") out[k] = v;
    });
    return out;
  }, [params]);

  return (
    <Box>
      <PageHeader title="Reportes"
        subtitle="Reportes operacionales y de gestión en PDF, Word y Excel. Respetan los datos que su rol puede ver." />
      <ErrorAlert error={catalog.error} />
      {!canExport && <Alert severity="info" sx={{ mb: 2 }}>Su rol puede consultar el historial, pero no generar reportes.</Alert>}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper variant="outlined">
            <List dense aria-label="Catálogo de reportes">
              {KIND_ORDER.map((kind) => {
                const items = defs.filter((d) => d.kind === kind);
                if (!items.length) return null;
                return (
                  <li key={kind}>
                    <ul style={{ padding: 0 }}>
                      <ListSubheader>{KIND_TITLES[kind]}</ListSubheader>
                      {items.map((d) => (
                        <ListItemButton key={d.code} selected={selected?.code === d.code}
                          aria-current={selected?.code === d.code ? "true" : undefined}
                          onClick={() => { setParams({ reporte: d.code }); setSentMessage(null); request.reset(); }}>
                          <ListItemText primary={<><strong>{d.code}</strong> · {d.title}</>}
                            secondary={d.available_from_phase ? `Datos desde la Fase ${d.available_from_phase}` : undefined} />
                        </ListItemButton>
                      ))}
                    </ul>
                  </li>
                );
              })}
            </List>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 8 }}>
          {selected && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                <Typography variant="h2" component="h2">{selected.code} · {selected.title}</Typography>
                <Chip size="small" label={selected.kind_label} />
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{selected.description}</Typography>
              <ErrorAlert error={request.error ?? options.error} />
              {sentMessage && <Alert severity="success" sx={{ mb: 2 }} role="status">{sentMessage}</Alert>}
              {canExport ? (
                <ReportForm definition={selected} options={options.data} initial={initial} busy={request.isPending}
                  onSubmit={(format, filters) => {
                    setSentMessage(null);
                    request.mutate({ code: selected.code, format, filters }, {
                      onSuccess: () => setSentMessage(
                        `${selected.code} en ${FORMAT_LABELS[format]} enviado. Aparecerá como "Listo" en el historial ` +
                        "y recibirá una notificación."),
                    });
                  }} />
              ) : null}
            </Paper>
          )}
        </Grid>
      </Grid>
      <ReportHistory />
    </Box>
  );
}
