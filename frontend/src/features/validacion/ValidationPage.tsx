import { useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  LinearProgress,
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
import { api } from "../../api/client";
import type { Diagnosis, LabelCatalog, Page } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import DiagnosisResult from "../../components/DiagnosisResult";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import { CATEGORY_COLOR, CATEGORY_LABEL, percent } from "../../utils/diagnosis";
import { formatDateTime } from "../../utils/format";
import { useCatalog } from "../parcelas/ParcelsPage";

export default function ValidationPage() {
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const [open, setOpen] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const q = useQuery({
    queryKey: ["pendientes", page, size],
    queryFn: () => api<Page<Diagnosis>>("/validacion/pendientes", { query: { page: page + 1, size } }),
    placeholderData: keepPreviousData,
  });

  return (
    <Box>
      <PageHeader title="Validación por experto"
        subtitle="Casos pendientes de su alcance. Primero los de confianza baja; luego por antigüedad. Sus etiquetas alimentan el reentrenamiento." />
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}
      <ErrorAlert error={q.error} />
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label="Casos pendientes de validación">
          <TableHead>
            <TableRow>
              <TableCell>Fecha</TableCell>
              <TableCell>Parcela</TableCell>
              <TableCell>Categoría predicha</TableCell>
              <TableCell align="right">Confianza</TableCell>
              <TableCell>Prioridad</TableCell>
              <TableCell align="right" />
            </TableRow>
          </TableHead>
          <TableBody>
            {q.data?.items.map((d) => (
              <TableRow key={d.id} hover>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDateTime(d.created_at)}</TableCell>
                <TableCell>{d.parcel.code} · {d.parcel.name}</TableCell>
                <TableCell><Chip size="small" label={CATEGORY_LABEL[d.category]} color={CATEGORY_COLOR[d.category]} /></TableCell>
                <TableCell align="right">{percent(d.confidence)}</TableCell>
                <TableCell>{d.requires_review ? <Chip size="small" color="warning" label="Confianza baja" /> : "Confirmación"}</TableCell>
                <TableCell align="right"><Button size="small" variant="outlined" onClick={() => setOpen(d.id)}>Revisar</Button></TableCell>
              </TableRow>
            ))}
            {q.data?.items.length === 0 && <TableRow><TableCell colSpan={6} align="center">No hay casos pendientes</TableCell></TableRow>}
          </TableBody>
        </Table>
        <TablePagination component="div" count={q.data?.total ?? 0} page={page} rowsPerPage={size}
          onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(e) => { setSize(Number(e.target.value)); setPage(0); }}
          rowsPerPageOptions={[10, 20, 50]} />
      </TableContainer>
      {open && <ReviewDialog id={open} onClose={() => setOpen(null)} onDone={(msg) => { setOpen(null); setNotice(msg); }} />}
    </Box>
  );
}

function ReviewDialog({ id, onClose, onDone }: { id: string; onClose(): void; onDone(msg: string): void }) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const d = useQuery({ queryKey: ["diagnostico", id], queryFn: () => api<Diagnosis>(`/diagnosticos/${id}`) });
  const labels = useQuery({ queryKey: ["etiquetas"], queryFn: () => api<LabelCatalog>("/diagnosticos/etiquetas"), staleTime: Infinity });
  const diseases = useCatalog("enfermedades");
  const [form, setForm] = useState({ final_label: "", evidence: "", differential_disease_id: "", notes: "" });
  const [error, setError] = useState<unknown>(null);
  const needsEvidence = form.final_label === "tizon_tardio_confirmado";
  const needsDifferential = form.final_label === "otra_enfermedad";
  const ready = !!form.final_label && (!needsEvidence || !!form.evidence) && (!needsDifferential || !!form.differential_disease_id);

  async function submit() {
    setError(null);
    try {
      await api(`/diagnosticos/${id}/revision`, {
        method: "POST",
        body: {
          final_label: form.final_label,
          evidence: form.evidence || null,
          differential_disease_id: form.differential_disease_id ? Number(form.differential_disease_id) : null,
          notes: form.notes || null,
        },
      });
      qc.invalidateQueries({ queryKey: ["pendientes"] });
      qc.invalidateQueries({ queryKey: ["diagnosticos"] });
      onDone("Validación registrada en la bitácora.");
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="lg" fullWidth aria-labelledby="review-title">
      <DialogTitle id="review-title">Revisión del especialista</DialogTitle>
      <DialogContent>
        {d.data ? <DiagnosisResult diagnosis={d.data} /> : <LinearProgress />}
        <Divider sx={{ my: 2 }} />
        <Typography variant="h3" gutterBottom>Su dictamen</Typography>
        <ErrorAlert error={error} />
        {!can("validacion:aprobar") ? (
          <Alert severity="info">Su rol puede ver la bandeja pero no registrar validaciones.</Alert>
        ) : (
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField select label="Etiqueta final" value={form.final_label} required
                onChange={(e) => setForm({ ...form, final_label: e.target.value })}>
                {Object.entries(labels.data?.etiquetas_finales ?? {}).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
              </TextField>
            </Grid>
            {needsEvidence && (
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField select label="Evidencia de la confirmación" value={form.evidence} required
                  helperText="«Confirmado» exige evidencia más allá de la imagen."
                  onChange={(e) => setForm({ ...form, evidence: e.target.value })}>
                  {Object.entries(labels.data?.evidencias ?? {}).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
                </TextField>
              </Grid>
            )}
            {needsDifferential && (
              <Grid size={{ xs: 12, md: 6 }}>
                <TextField select label="Enfermedad o daño observado" value={form.differential_disease_id} required
                  onChange={(e) => setForm({ ...form, differential_disease_id: e.target.value })}>
                  {diseases.data?.filter((x) => !x.is_target).map((x) => (
                    <MenuItem key={x.id} value={String(x.id)}>{x.name}{x.causal_agent ? ` (${x.causal_agent})` : ""}</MenuItem>
                  ))}
                </TextField>
              </Grid>
            )}
            <Grid size={12}>
              <TextField label="Notas" value={form.notes} multiline minRows={2}
                onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Grid>
          </Grid>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancelar</Button>
        {can("validacion:aprobar") && <Button variant="contained" onClick={submit} disabled={!ready}>Registrar validación</Button>}
      </DialogActions>
    </Dialog>
  );
}
