import { useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import { api, downloadFile } from "../../api/client";
import type { Page, ReportJob } from "../../api/types";
import ErrorAlert from "../../components/ErrorAlert";
import { formatDateTime } from "../../utils/format";
import { formatBytes, FORMAT_LABELS, isFinished, STATUS_COLORS, STATUS_LABELS, useNotifyWhenFinished } from "./useReports";

export function filtersSummary(filters: Record<string, string | number>): string {
  const entries = Object.entries(filters);
  return entries.length ? entries.map(([k, v]) => `${k}: ${v}`).join(" · ") : "Sin filtros";
}

export function DownloadButton({ job, size = "small" }: { job: ReportJob; size?: "small" | "medium" }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  return (
    <>
      <Button size={size} variant="outlined" startIcon={<DownloadIcon />} disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await downloadFile(`/reportes/${job.id}/descarga`, job.file_name ?? `${job.report_code}.${job.format}`);
            void qc.invalidateQueries({ queryKey: ["reportes", "historial"] });
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}>
        Descargar
      </Button>
      {!!error && <Box sx={{ mt: 1 }}><ErrorAlert error={error} /></Box>}
    </>
  );
}

export default function ReportHistory() {
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(10);
  const q = useQuery({
    queryKey: ["reportes", "historial", page, size],
    queryFn: () => api<Page<ReportJob>>("/reportes", { query: { page: page + 1, size }, background: true }),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.items.some((j) => !isFinished(j.status)) ? 2000 : false),
  });
  useNotifyWhenFinished(q.data?.items ?? []);

  return (
    <Paper variant="outlined">
      <Box sx={{ p: 2, pb: 0 }}>
        <Typography variant="h2" component="h2">Historial de reportes</Typography>
        <Typography variant="body2" color="text.secondary">
          Reportes que usted solicitó. Los archivos se generan en segundo plano y quedan disponibles para descargar.
        </Typography>
      </Box>
      <Box sx={{ p: 2 }}><ErrorAlert error={q.error} /></Box>
      <TableContainer>
        <Table size="small" aria-label="Historial de reportes">
          <TableHead>
            <TableRow>
              <TableCell>Solicitado</TableCell>
              <TableCell>Reporte</TableCell>
              <TableCell>Formato</TableCell>
              <TableCell>Estado</TableCell>
              <TableCell align="right">Filas</TableCell>
              <TableCell align="right">Tamaño</TableCell>
              <TableCell align="right">Descargas</TableCell>
              <TableCell align="right">Acción</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {q.isLoading && (
              <TableRow><TableCell colSpan={8}><CircularProgress size={20} aria-label="Cargando" /></TableCell></TableRow>
            )}
            {q.data?.items.length === 0 && (
              <TableRow><TableCell colSpan={8}>Todavía no ha generado reportes.</TableCell></TableRow>
            )}
            {q.data?.items.map((j) => (
              <TableRow key={j.id} hover>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDateTime(j.created_at)}</TableCell>
                <TableCell>
                  <Tooltip title={filtersSummary(j.filters)}>
                    <span><strong>{j.report_code}</strong> {j.report_title}</span>
                  </Tooltip>
                </TableCell>
                <TableCell>{FORMAT_LABELS[j.format]}</TableCell>
                <TableCell>
                  <Tooltip title={j.error ?? ""} disableHoverListener={!j.error}>
                    <Chip size="small" color={STATUS_COLORS[j.status]} label={STATUS_LABELS[j.status]}
                      icon={isFinished(j.status) ? undefined : <CircularProgress size={12} color="inherit" />} />
                  </Tooltip>
                </TableCell>
                <TableCell align="right">{j.row_count ?? "—"}</TableCell>
                <TableCell align="right">{formatBytes(j.size_bytes)}</TableCell>
                <TableCell align="right">{j.download_count}</TableCell>
                <TableCell align="right">{j.status === "listo" ? <DownloadButton job={j} /> : null}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <TablePagination component="div" count={q.data?.total ?? 0} page={page} rowsPerPage={size}
        rowsPerPageOptions={[10, 20, 50]} onPageChange={(_, p) => setPage(p)}
        onRowsPerPageChange={(e) => { setSize(Number(e.target.value)); setPage(0); }} />
    </Paper>
  );
}
