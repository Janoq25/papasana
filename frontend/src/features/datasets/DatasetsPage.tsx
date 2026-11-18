import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Grid,
  IconButton,
  Link,
  MenuItem,
  Paper,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import { api, downloadFile } from "../../api/client";
import type { DatasetEntry, LicenseStatus } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import { CLASS_LABEL } from "../../utils/diagnosis";
import { formatDateTime } from "../../utils/format";

export const LICENSE_LABEL: Record<LicenseStatus, string> = {
  por_verificar: "Por verificar",
  verificada: "Verificada",
  rechazada: "Rechazada",
};
const LICENSE_COLOR: Record<LicenseStatus, "warning" | "success" | "error"> = {
  por_verificar: "warning",
  verificada: "success",
  rechazada: "error",
};
const CONDITIONS = { laboratorio: "Laboratorio", campo: "Campo", mixto: "Mixto", sintetico: "Sintético" };
const ROLES = {
  entrenamiento: "Entrenamiento",
  validacion_externa: "Validación externa",
  validacion_prospectiva: "Validación prospectiva",
  prueba_de_humo: "Prueba de humo",
};
const ETIOLOGY = { no: "No", parcial: "Parcial", si: "Sí" };
const CLASSES = ["sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar"];

type Form = {
  code: string; name: string; version: string; source_url: string; citation: string;
  conditions: DatasetEntry["conditions"]; etiological_confirmation: DatasetEntry["etiological_confirmation"];
  has_group_ids: boolean; role: DatasetEntry["role"]; n_images: string; notes: string;
  class_map: [string, string][];
};

const emptyForm: Form = {
  code: "", name: "", version: "", source_url: "", citation: "", conditions: "campo", etiological_confirmation: "no",
  has_group_ids: false, role: "validacion_externa", n_images: "", notes: "", class_map: [["", "sano"]],
};

function toForm(d: DatasetEntry): Form {
  return {
    code: d.code, name: d.name, version: d.version ?? "", source_url: d.source_url ?? "", citation: d.citation ?? "",
    conditions: d.conditions, etiological_confirmation: d.etiological_confirmation, has_group_ids: d.has_group_ids,
    role: d.role, n_images: d.n_images?.toString() ?? "", notes: d.notes ?? "", class_map: Object.entries(d.class_map),
  };
}

function toBody(f: Form, creating: boolean) {
  const body: Record<string, unknown> = {
    name: f.name.trim(), version: f.version.trim() || null, source_url: f.source_url.trim() || null,
    citation: f.citation.trim() || null, conditions: f.conditions, etiological_confirmation: f.etiological_confirmation,
    has_group_ids: f.has_group_ids, role: f.role, n_images: f.n_images ? Number(f.n_images) : null,
    notes: f.notes.trim() || null,
    class_map: Object.fromEntries(f.class_map.filter(([k]) => k.trim()).map(([k, v]) => [k.trim(), v])),
  };
  if (creating) body.code = f.code.trim();
  return body;
}

/** Se monta solo mientras está abierto (con `key`), así cada apertura parte del estado guardado. */
function DatasetDialog({ editing, onClose }: { editing: DatasetEntry | null; onClose(): void }) {
  const qc = useQueryClient();
  const [f, setF] = useState<Form>(() => (editing ? toForm(editing) : emptyForm));
  const m = useMutation({
    mutationFn: () => editing
      ? api<DatasetEntry>(`/datasets/${editing.id}`, { method: "PATCH", body: toBody(f, false) })
      : api<DatasetEntry>("/datasets", { method: "POST", body: toBody(f, true) }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["datasets"] }); onClose(); },
  });
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>{editing ? `Editar ${editing.code}` : "Registrar dataset"}</DialogTitle>
      <DialogContent dividers>
        {!editing && (
          <Alert severity="info" sx={{ mb: 2 }}>
            El dataset se registra con la licencia <strong>por verificar</strong>: no se puede usar para entrenar hasta
            que alguien revise la licencia en la fuente oficial.
          </Alert>
        )}
        <ErrorAlert error={m.error} />
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField label="Código" value={f.code} onChange={set("code")} disabled={!!editing} required
              helperText="Minúsculas, números y guion bajo" />
          </Grid>
          <Grid size={{ xs: 12, sm: 8 }}><TextField label="Nombre" value={f.name} onChange={set("name")} required /></Grid>
          <Grid size={{ xs: 6, sm: 3 }}><TextField label="Versión" value={f.version} onChange={set("version")} /></Grid>
          <Grid size={{ xs: 6, sm: 3 }}><TextField label="N.° de imágenes" type="number" value={f.n_images} onChange={set("n_images")} /></Grid>
          <Grid size={{ xs: 12, sm: 6 }}><TextField label="URL de la fuente" value={f.source_url} onChange={set("source_url")} /></Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField select label="Condiciones" value={f.conditions} onChange={set("conditions")}>
              {Object.entries(CONDITIONS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField select label="Uso en el estudio" value={f.role} onChange={set("role")}>
              {Object.entries(ROLES).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField select label="Confirmación etiológica" value={f.etiological_confirmation} onChange={set("etiological_confirmation")}>
              {Object.entries(ETIOLOGY).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12 }}>
            <FormControlLabel label="Publica IDs de planta, parcela o procedencia (permite agrupar los splits)"
              control={<Switch checked={f.has_group_ids} onChange={(e) => setF({ ...f, has_group_ids: e.target.checked })} />} />
          </Grid>
          <Grid size={{ xs: 12 }}><TextField label="Cita" multiline minRows={2} value={f.citation} onChange={set("citation")} /></Grid>
          <Grid size={{ xs: 12 }}>
            <Typography variant="subtitle2">Mapeo de etiquetas a clases por síntoma (D-01)</Typography>
            <Typography variant="caption" color="text.secondary" component="p" sx={{ mb: 1 }}>
              "Early blight" (Alternaria) es otra enfermedad foliar, nunca tizón tardío.
            </Typography>
            {f.class_map.map(([k, v], i) => (
              <Box key={i} sx={{ display: "flex", gap: 1, mb: 1 }}>
                <TextField label="Etiqueta en la fuente" value={k}
                  onChange={(e) => setF({ ...f, class_map: f.class_map.map((p, j) => (j === i ? [e.target.value, p[1]] : p)) })} />
                <TextField select label="Clase" value={v}
                  onChange={(e) => setF({ ...f, class_map: f.class_map.map((p, j) => (j === i ? [p[0], e.target.value] : p)) })}>
                  {CLASSES.map((c) => <MenuItem key={c} value={c}>{CLASS_LABEL[c]}</MenuItem>)}
                </TextField>
                <IconButton aria-label="Quitar fila" onClick={() => setF({ ...f, class_map: f.class_map.filter((_, j) => j !== i) })}>
                  <DeleteIcon />
                </IconButton>
              </Box>
            ))}
            <Button size="small" startIcon={<AddIcon />} onClick={() => setF({ ...f, class_map: [...f.class_map, ["", "sano"]] })}>
              Agregar etiqueta
            </Button>
          </Grid>
          <Grid size={{ xs: 12 }}><TextField label="Notas" multiline minRows={2} value={f.notes} onChange={set("notes")} /></Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="contained" disabled={m.isPending || !f.name.trim() || (!editing && !f.code.trim())} onClick={() => m.mutate()}>
          Guardar
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function LicenseDialog({ dataset, onClose }: { dataset: DatasetEntry; onClose(): void }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<LicenseStatus>("verificada");
  const [license, setLicense] = useState(dataset.license ?? "");
  const [url, setUrl] = useState(dataset.license_url ?? "");
  const [notes, setNotes] = useState("");
  const m = useMutation({
    mutationFn: () => api<DatasetEntry>(`/datasets/${dataset.id}/licencia`, {
      method: "PUT", body: { license_status: status, license: license || null, license_url: url || null, license_notes: notes || null },
    }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["datasets"] }); onClose(); },
  });
  const incomplete = status === "verificada" ? !license.trim() || !url.trim() || !notes.trim()
    : status === "rechazada" ? !notes.trim() : false;
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Revisión de la licencia · {dataset.name}</DialogTitle>
      <DialogContent dividers>
        {dataset.license_notes && <Alert severity="info" sx={{ mb: 2 }}>{dataset.license_notes}</Alert>}
        <Typography variant="body2" sx={{ mb: 2 }}>
          Registre la licencia tal como la declara la <strong>fuente oficial</strong> (repositorio o página de los
          autores), no la de una copia de terceros. Su nombre y la fecha quedan como responsables de la verificación.
        </Typography>
        <ErrorAlert error={m.error} />
        <Grid container spacing={2}>
          <Grid size={{ xs: 12 }}>
            <TextField select label="Resultado" value={status} onChange={(e) => setStatus(e.target.value as LicenseStatus)}>
              {Object.entries(LICENSE_LABEL).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 5 }}><TextField label="Licencia (p. ej., CC BY 4.0)" value={license} onChange={(e) => setLicense(e.target.value)} /></Grid>
          <Grid size={{ xs: 12, sm: 7 }}><TextField label="Enlace a la licencia en la fuente oficial" value={url} onChange={(e) => setUrl(e.target.value)} /></Grid>
          <Grid size={{ xs: 12 }}>
            <TextField label="Qué revisó y qué permite la licencia" multiline minRows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="contained" disabled={m.isPending || incomplete} onClick={() => m.mutate()}>Registrar revisión</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function DatasetsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["datasets"], queryFn: () => api<DatasetEntry[]>("/datasets") });
  const [editing, setEditing] = useState<DatasetEntry | null>(null);
  const [creating, setCreating] = useState(false);
  const [licensing, setLicensing] = useState<DatasetEntry | null>(null);
  const [exportError, setExportError] = useState<unknown>(null);
  const del = useMutation({
    mutationFn: (id: number) => api(`/datasets/${id}`, { method: "DELETE" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["datasets"] }),
  });
  const pending = (q.data ?? []).filter((d) => d.license_status === "por_verificar" && d.is_active).length;

  return (
    <Box>
      <PageHeader title="Datasets y licencias"
        subtitle="Registro obligatorio antes de usar datos: fuente, licencia verificada, cita y tipo de etiqueta."
        actions={
          <Box sx={{ display: "flex", gap: 1 }}>
            {can("datasets:exportar") && (
              <Button variant="outlined" startIcon={<FileDownloadIcon />} onClick={async () => {
                setExportError(null);
                try { await downloadFile("/datasets/exportar", "datasets.yaml"); } catch (e) { setExportError(e); }
              }}>Exportar datasets.yaml</Button>
            )}
            {can("datasets:crear") && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreating(true)}>Registrar</Button>}
          </Box>
        } />
      <ErrorAlert error={q.error ?? del.error ?? exportError} />
      {pending > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {pending} dataset(s) con la licencia <strong>por verificar</strong>. El pipeline de entrenamiento se niega a
          usarlos hasta que se registre la verificación (y se exporte <code>ml/datasets.yaml</code>).
        </Alert>
      )}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label="Registro de datasets">
          <TableHead><TableRow>
            <TableCell>Dataset</TableCell><TableCell>Condiciones</TableCell><TableCell>Uso</TableCell>
            <TableCell>Licencia</TableCell><TableCell>Verificación</TableCell><TableCell align="right">Imágenes</TableCell>
            <TableCell align="right">Acciones</TableCell>
          </TableRow></TableHead>
          <TableBody>
            {q.data?.map((d) => (
              <TableRow key={d.id} sx={{ opacity: d.is_active ? 1 : 0.6 }}>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{d.name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {d.code}{d.version ? ` · v${d.version}` : ""}{d.source_url && <> · <Link href={d.source_url} target="_blank" rel="noreferrer">fuente</Link></>}
                  </Typography>
                </TableCell>
                <TableCell>{CONDITIONS[d.conditions]}</TableCell>
                <TableCell>{ROLES[d.role]}</TableCell>
                <TableCell>
                  <Chip size="small" color={LICENSE_COLOR[d.license_status]} label={LICENSE_LABEL[d.license_status]} />
                  <Typography variant="caption" component="div">
                    {d.license_url ? <Link href={d.license_url} target="_blank" rel="noreferrer">{d.license ?? "ver"}</Link> : (d.license ?? "Sin licencia registrada")}
                  </Typography>
                </TableCell>
                <TableCell>
                  {d.license_verified_at
                    ? <Typography variant="caption">{d.license_verified_by_name} · {formatDateTime(d.license_verified_at)}</Typography>
                    : <Typography variant="caption" color="text.secondary">{d.license_status === "verificada" ? "Generado por el propio código" : "—"}</Typography>}
                </TableCell>
                <TableCell align="right">{d.n_images ?? "—"}</TableCell>
                <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                  {can("datasets:editar") && <Button size="small" onClick={() => setLicensing(d)}>Licencia</Button>}
                  {can("datasets:editar") && <Button size="small" onClick={() => setEditing(d)}>Editar</Button>}
                  {can("datasets:eliminar") && (
                    <Tooltip title="Eliminar (solo si ningún modelo lo usa)">
                      <IconButton size="small" aria-label={`Eliminar ${d.code}`} onClick={() => {
                        if (window.confirm(`¿Eliminar el dataset ${d.code}?`)) del.mutate(d.id);
                      }}><DeleteIcon fontSize="small" /></IconButton>
                    </Tooltip>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {(creating || editing) && (
        <DatasetDialog key={editing?.id ?? "nuevo"} editing={editing}
          onClose={() => { setCreating(false); setEditing(null); }} />
      )}
      {licensing && <LicenseDialog key={licensing.id} dataset={licensing} onClose={() => setLicensing(null)} />}
    </Box>
  );
}
