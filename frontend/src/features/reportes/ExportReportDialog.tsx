import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  LinearProgress,
  Radio,
  RadioGroup,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import type { ReportFormat } from "../../api/types";
import ErrorAlert from "../../components/ErrorAlert";
import { DownloadButton, filtersSummary } from "./ReportHistory";
import { cleanFilters, FORMAT_LABELS, STATUS_LABELS, useReportCatalog, useReportJob, useRequestReport } from "./useReports";

interface Props {
  open: boolean;
  onClose(): void;
  /** Reportes que se ofrecen (el primero va seleccionado); se muestran solo los que el usuario puede generar. */
  codes: string[];
  /** Filtros de la pantalla actual; se envían solo los que admite el reporte elegido. */
  filters: Record<string, string>;
  title?: string;
}

/** Exporta la vista actual (bitácora, dashboard) con el mismo mecanismo de reportes en segundo plano. */
export default function ExportReportDialog({ open, onClose, codes, filters, title = "Exportar" }: Props) {
  const catalog = useReportCatalog(open);
  const available = (catalog.data ?? []).filter((d) => codes.includes(d.code))
    .sort((a, b) => codes.indexOf(a.code) - codes.indexOf(b.code));
  const [code, setCode] = useState<string>("");
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const [jobId, setJobId] = useState<string | null>(null);
  const request = useRequestReport();
  const job = useReportJob(jobId);
  const definition = available.find((d) => d.code === code) ?? available[0];
  const sent = definition ? cleanFilters(filters, definition.filters.map((f) => f.key)) : {};

  useEffect(() => {
    if (!open) {
      setJobId(null);
      request.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const status = job.data?.status;
  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" aria-labelledby="export-title">
      <DialogTitle id="export-title">{title}</DialogTitle>
      <DialogContent>
        <ErrorAlert error={catalog.error ?? request.error ?? job.error} />
        {catalog.isSuccess && available.length === 0 && (
          <Alert severity="warning">No tiene permiso para generar estos reportes.</Alert>
        )}
        {definition && !jobId && (
          <>
            {available.length > 1 && (
              <RadioGroup value={definition.code} onChange={(e) => setCode(e.target.value)} aria-label="Reporte">
                {available.map((d) => (
                  <FormControlLabel key={d.code} value={d.code} control={<Radio />}
                    label={<><strong>{d.code}</strong> {d.title}</>} />
                ))}
              </RadioGroup>
            )}
            {available.length === 1 && (
              <Typography sx={{ mb: 1 }}><strong>{definition.code}</strong> · {definition.title}</Typography>
            )}
            <Typography variant="body2" color="text.secondary" sx={{ my: 1 }}>
              Filtros: {filtersSummary(sent)}
            </Typography>
            <ToggleButtonGroup exclusive size="small" value={format} aria-label="Formato"
              onChange={(_, v: ReportFormat | null) => v && setFormat(v)}>
              {definition.formats.map((f) => (
                <ToggleButton key={f} value={f}>{FORMAT_LABELS[f]}</ToggleButton>
              ))}
            </ToggleButtonGroup>
          </>
        )}
        {jobId && (
          <>
            <Typography sx={{ mb: 1 }} role="status" aria-live="polite">
              Estado: {status ? STATUS_LABELS[status] : "Enviando…"}
            </Typography>
            {status !== "listo" && status !== "error" && <LinearProgress aria-label="Generando el reporte" />}
            {status === "error" && <Alert severity="error">{job.data?.error ?? "No se pudo generar el reporte."}</Alert>}
            {status === "listo" && job.data && <DownloadButton job={job.data} size="medium" />}
            <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 2 }}>
              Puede cerrar esta ventana: el archivo también queda en el historial del módulo Reportes y recibirá una
              notificación cuando esté listo.
            </Typography>
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cerrar</Button>
        {!jobId && (
          <Button variant="contained" disabled={!definition || request.isPending}
            onClick={() => definition && request.mutate({ code: definition.code, format, filters: sent },
              { onSuccess: (j) => setJobId(j.id) })}>
            Generar
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
