import { useEffect, useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Grid,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import { api } from "../../api/client";
import type { Batch, Diagnosis, Page, ParcelOption } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Can } from "../../auth/RequirePermission";
import DiagnosisResult from "../../components/DiagnosisResult";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import { CATEGORY_COLOR, CATEGORY_LABEL, percent, STATUS_LABEL } from "../../utils/diagnosis";
import { formatDateTime } from "../../utils/format";

export function useParcelOptions() {
  return useQuery({ queryKey: ["parcelas-opciones"], queryFn: () => api<ParcelOption[]>("/parcelas/opciones") });
}

function getPosition(): Promise<{ lat: number; lon: number } | null> {
  if (!("geolocation" in navigator)) return Promise.resolve(null);
  return new Promise((resolve) =>
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    ),
  );
}

export default function DiagnosisPage() {
  return (
    <Box>
      <PageHeader title="Captura y diagnóstico"
        subtitle="Suba fotografías de hojas tomadas en campo. El resultado describe síntomas y debe ser revisado por un especialista." />
      <Can permission="diagnostico:crear">
        <UploadCard />
      </Can>
      <History />
    </Box>
  );
}

function UploadCard() {
  const qc = useQueryClient();
  const parcels = useParcelOptions();
  const [parcelId, setParcelId] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [useDevice, setUseDevice] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<Diagnosis | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchResults, setBatchResults] = useState<Batch["results"]>([]);

  async function submit() {
    setError(null);
    setResult(null);
    setBatchId(null);
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("parcel_id", parcelId);
      if (useDevice) {
        const pos = await getPosition();
        if (pos) {
          fd.append("lat", String(pos.lat));
          fd.append("lon", String(pos.lon));
          fd.append("gps_source", "dispositivo");
        }
      }
      if (files.length === 1) {
        fd.append("file", files[0]);
        setResult(await api<Diagnosis>("/diagnosticos", { method: "POST", form: fd }));
      } else {
        files.forEach((f) => fd.append("files", f));
        const b = await api<Batch>("/diagnosticos/lote", { method: "POST", form: fd });
        setBatchResults(b.results);
        setBatchId(b.id);
      }
      setFiles([]);
      qc.invalidateQueries({ queryKey: ["diagnosticos"] });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card variant="outlined" sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h2" gutterBottom>Nueva captura</Typography>
        <Grid container spacing={2} sx={{ alignItems: "center" }}>
          <Grid size={{ xs: 12, md: 4 }}>
            <TextField select label="Parcela" value={parcelId} onChange={(e) => setParcelId(e.target.value)} required
              helperText={parcels.data?.length === 0 ? "No tiene parcelas asignadas." : " "}>
              {parcels.data?.map((p) => <MenuItem key={p.id} value={String(p.id)}>{p.code} · {p.name}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <Button component="label" variant="outlined" startIcon={<CloudUploadIcon />} fullWidth sx={{ py: 1 }}>
              {files.length ? `${files.length} foto(s) seleccionada(s)` : "Seleccionar o tomar fotos"}
              <input hidden type="file" multiple accept="image/jpeg,image/png,image/webp" capture="environment"
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
            </Button>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
              JPEG, PNG o WebP · máx. 15 MB por foto · una foto = resultado inmediato; varias = lote en segundo plano
            </Typography>
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <FormControlLabel control={<Checkbox checked={useDevice} onChange={(e) => setUseDevice(e.target.checked)} />}
              label="Usar la ubicación del dispositivo si la foto no tiene GPS" />
            <Button variant="contained" fullWidth onClick={submit} disabled={busy || !parcelId || files.length === 0}>
              {busy ? "Procesando…" : "Diagnosticar"}
            </Button>
          </Grid>
        </Grid>
        {busy && <LinearProgress sx={{ mt: 2 }} aria-label="Subiendo y analizando" />}
        <Box sx={{ mt: 2 }}>
          <ErrorAlert error={error} />
          {result && <DiagnosisResult diagnosis={result} />}
          {batchId && <BatchProgress batchId={batchId} results={batchResults} />}
        </Box>
      </CardContent>
    </Card>
  );
}

function BatchProgress({ batchId, results }: { batchId: string; results: Batch["results"] }) {
  const qc = useQueryClient();
  const batch = useQuery({
    queryKey: ["lote", batchId],
    queryFn: () => api<Batch>(`/diagnosticos/lotes/${batchId}`),
    refetchInterval: (query) => (query.state.data?.status === "completado" ? false : 2000),
  });
  const b = batch.data;
  const done = b ? b.processed + b.failed : 0;
  const completed = b?.status === "completado";
  useEffect(() => {
    if (completed) qc.invalidateQueries({ queryKey: ["diagnosticos"] });
  }, [completed, qc]);
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="h3" gutterBottom>Lote en proceso</Typography>
      {b && (
        <>
          <LinearProgress variant="determinate" value={b.total ? (done / b.total) * 100 : 100} sx={{ mb: 1 }}
            aria-label={`Procesadas ${done} de ${b.total}`} />
          <Typography variant="body2" aria-live="polite">
            {b.status === "completado" ? "Completado" : "Procesando"}: {b.processed} de {b.total} diagnosticadas
            {b.failed > 0 && ` · ${b.failed} con error`}
          </Typography>
        </>
      )}
      <List dense>
        {results.filter((r) => !r.aceptada).map((r) => (
          <ListItem key={r.archivo}><ListItemText primary={`${r.archivo}: rechazada`} secondary={r.motivo} /></ListItem>
        ))}
        {b?.diagnoses.map((d) => (
          <ListItem key={d.id}>
            <ListItemText primary={`${d.image.original_filename ?? d.id}: ${CATEGORY_LABEL[d.category]} (${percent(d.confidence)})`}
              secondary={STATUS_LABEL[d.status]} />
          </ListItem>
        ))}
      </List>
    </Paper>
  );
}

function History() {
  const { can } = useAuth();
  const parcels = useParcelOptions();
  const [filters, setFilters] = useState({ parcel_id: "", category: "", status: "" });
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const [open, setOpen] = useState<string | null>(null);
  const q = useQuery({
    queryKey: ["diagnosticos", filters, page, size],
    queryFn: () => api<Page<Diagnosis>>("/diagnosticos", { query: { ...filters, page: page + 1, size } }),
    placeholderData: keepPreviousData,
  });
  const set = (k: keyof typeof filters) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setFilters({ ...filters, [k]: e.target.value });
    setPage(0);
  };

  return (
    <Box>
      <Typography variant="h2" gutterBottom>Historial</Typography>
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <TextField select label="Parcela" value={filters.parcel_id} onChange={set("parcel_id")}>
              <MenuItem value="">Todas</MenuItem>
              {parcels.data?.map((p) => <MenuItem key={p.id} value={String(p.id)}>{p.code} · {p.name}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 6, md: 4 }}>
            <TextField select label="Categoría" value={filters.category} onChange={set("category")}>
              <MenuItem value="">Todas</MenuItem>
              {Object.entries(CATEGORY_LABEL).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 6, md: 4 }}>
            <TextField select label="Estado" value={filters.status} onChange={set("status")}>
              <MenuItem value="">Todos</MenuItem>
              {Object.entries(STATUS_LABEL).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
          </Grid>
        </Grid>
      </Paper>
      <ErrorAlert error={q.error} />
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label="Historial de diagnósticos">
          <TableHead>
            <TableRow>
              <TableCell>Fecha</TableCell>
              <TableCell>Parcela</TableCell>
              <TableCell>Categoría</TableCell>
              <TableCell align="right">Confianza</TableCell>
              <TableCell>Estado</TableCell>
              <TableCell>Modelo</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {q.data?.items.map((d) => (
              <TableRow key={d.id} hover onClick={() => setOpen(d.id)} sx={{ cursor: "pointer" }}
                tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setOpen(d.id)} aria-label={`Ver diagnóstico del ${formatDateTime(d.created_at)}`}>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDateTime(d.created_at)}</TableCell>
                <TableCell>{d.parcel.code}</TableCell>
                <TableCell><Chip size="small" label={CATEGORY_LABEL[d.category]} color={CATEGORY_COLOR[d.category]} /></TableCell>
                <TableCell align="right">{percent(d.confidence)}</TableCell>
                <TableCell>{STATUS_LABEL[d.status]}{d.requires_review && " · requiere revisión"}</TableCell>
                <TableCell>{d.model.is_demo ? <Chip size="small" color="error" variant="outlined" label="DEMO" /> : d.model.display_name}</TableCell>
              </TableRow>
            ))}
            {q.data?.items.length === 0 && <TableRow><TableCell colSpan={6} align="center">Sin diagnósticos</TableCell></TableRow>}
          </TableBody>
        </Table>
        <TablePagination component="div" count={q.data?.total ?? 0} page={page} rowsPerPage={size}
          onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(e) => { setSize(Number(e.target.value)); setPage(0); }}
          rowsPerPageOptions={[10, 20, 50]} />
      </TableContainer>
      {open && <DiagnosisDialog id={open} canVoid={can("diagnostico:eliminar")} onClose={() => setOpen(null)} />}
    </Box>
  );
}

export function DiagnosisDialog({ id, canVoid, onClose }: { id: string; canVoid: boolean; onClose(): void }) {
  const qc = useQueryClient();
  const d = useQuery({ queryKey: ["diagnostico", id], queryFn: () => api<Diagnosis>(`/diagnosticos/${id}`) });
  const [reason, setReason] = useState("");
  const [error, setError] = useState<unknown>(null);

  async function voidIt() {
    setError(null);
    try {
      await api(`/diagnosticos/${id}/anular`, { method: "POST", body: { reason } });
      await qc.invalidateQueries({ queryKey: ["diagnostico", id] });
      qc.invalidateQueries({ queryKey: ["diagnosticos"] });
      setReason("");
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="lg" fullWidth aria-labelledby="diag-title">
      <DialogTitle id="diag-title">Diagnóstico</DialogTitle>
      <DialogContent>
        <ErrorAlert error={error || d.error} />
        {d.data ? <DiagnosisResult diagnosis={d.data} /> : <LinearProgress />}
        {canVoid && d.data && d.data.status !== "anulado" && (
          <Box sx={{ display: "flex", gap: 1, mt: 2 }}>
            <TextField label="Motivo de anulación" value={reason} onChange={(e) => setReason(e.target.value)} />
            <Button color="error" variant="outlined" onClick={voidIt} disabled={reason.trim().length < 5}>Anular</Button>
          </Box>
        )}
        {d.data?.status === "anulado" && <Alert severity="info" sx={{ mt: 2 }}>Los diagnósticos anulados se conservan para la trazabilidad.</Alert>}
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Cerrar</Button></DialogActions>
    </Dialog>
  );
}
