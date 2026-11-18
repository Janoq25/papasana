import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import BlockIcon from "@mui/icons-material/Block";
import EditIcon from "@mui/icons-material/Edit";
import { api } from "../../api/client";
import type { CatalogItem, Ubigeo } from "../../api/types";
import { Can } from "../../auth/RequirePermission";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import { useRegions } from "../perfil/ProfilePage";

type CatalogName = "variedades" | "estadios" | "enfermedades";

interface FieldDef {
  key: keyof CatalogItem;
  label: string;
  multiline?: boolean;
  options?: [string, string][];
  type?: "number";
}

const FIELDS: Record<CatalogName, FieldDef[]> = {
  variedades: [
    { key: "name", label: "Nombre" },
    { key: "group", label: "Grupo", options: [["", "Sin especificar"], ["nativa", "Nativa"], ["mejorada", "Mejorada"]] },
    { key: "late_blight_susceptibility", label: "Susceptibilidad al tizón tardío",
      options: [["", "Sin dato verificado"], ["alta", "Alta"], ["media", "Media"], ["baja", "Baja"]] },
    { key: "source", label: "Fuente de la susceptibilidad (obligatoria si se indica)", multiline: true },
  ],
  estadios: [
    { key: "name", label: "Nombre" },
    { key: "code", label: "Código (minúsculas y guion bajo)" },
    { key: "sort_order", label: "Orden", type: "number" },
    { key: "description", label: "Descripción", multiline: true },
  ],
  enfermedades: [
    { key: "name", label: "Nombre" },
    { key: "causal_agent", label: "Agente causal" },
    { key: "key_symptoms", label: "Síntomas clave", multiline: true },
    { key: "distinguishing_features", label: "Rasgos que la distinguen", multiline: true },
    { key: "source", label: "Fuente", multiline: true },
  ],
};

const TITLES: Record<CatalogName, string> = {
  variedades: "Variedades de papa",
  estadios: "Estadios fenológicos",
  enfermedades: "Enfermedades diferenciales",
};

export default function CatalogsPage() {
  const [tab, setTab] = useState<CatalogName | "ubigeo">("variedades");
  return (
    <Box>
      <PageHeader title="Catálogos" subtitle="Datos de referencia usados en parcelas, diagnóstico y validación experta." />
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }} variant="scrollable" aria-label="Catálogos">
        <Tab value="variedades" label="Variedades" />
        <Tab value="estadios" label="Estadios fenológicos" />
        <Tab value="enfermedades" label="Enfermedades diferenciales" />
        <Tab value="ubigeo" label="Ubigeo" />
      </Tabs>
      {tab === "ubigeo" ? <UbigeoTab /> : <CatalogTab key={tab} name={tab} />}
    </Box>
  );
}

function CatalogTab({ name }: { name: CatalogName }) {
  const qc = useQueryClient();
  const items = useQuery({
    queryKey: ["catalogo", name, "todos"],
    queryFn: () => api<CatalogItem[]>(`/catalogos/${name}`, { query: { include_inactive: true } }),
  });
  const [editing, setEditing] = useState<CatalogItem | "new" | null>(null);
  const [error, setError] = useState<unknown>(null);
  const fields = FIELDS[name];

  async function deactivate(item: CatalogItem) {
    if (!window.confirm(`¿Desactivar «${item.name}»? Seguirá visible en los registros existentes.`)) return;
    setError(null);
    try {
      await api(`/catalogos/${name}/${item.id}`, { method: "DELETE" });
      qc.invalidateQueries({ queryKey: ["catalogo", name] });
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Box>
      <Stack direction="row" sx={{ mb: 1, alignItems: "center" }}>
        <Typography variant="h2" sx={{ flexGrow: 1 }}>{TITLES[name]}</Typography>
        <Can permission="catalogos:crear"><Button variant="contained" onClick={() => setEditing("new")}>Agregar</Button></Can>
      </Stack>
      {name === "enfermedades" && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Descripciones generales de referencia para el diagnóstico diferencial. Contrastarlas con material técnico de INIA,
          SENASA o FAO antes de usarlas en el artículo.
        </Alert>
      )}
      <ErrorAlert error={error || items.error} />
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label={TITLES[name]}>
          <TableHead>
            <TableRow>
              {fields.slice(0, 3).map((f) => <TableCell key={f.key}>{f.label}</TableCell>)}
              <TableCell>Estado</TableCell>
              <TableCell align="right">Acciones</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.data?.map((it) => (
              <TableRow key={it.id} hover>
                {fields.slice(0, 3).map((f) => (
                  <TableCell key={f.key} sx={{ maxWidth: 360 }}>
                    {String(it[f.key] ?? "—")}
                    {f.key === "name" && it.is_target && <Chip size="small" color="error" label="Objetivo" sx={{ ml: 1 }} />}
                  </TableCell>
                ))}
                <TableCell><Chip size="small" label={it.is_active ? "Activo" : "Inactivo"} color={it.is_active ? "success" : "default"} /></TableCell>
                <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                  <Can permission="catalogos:editar">
                    <Tooltip title="Editar"><IconButton size="small" aria-label={`Editar ${it.name}`} onClick={() => setEditing(it)}><EditIcon fontSize="small" /></IconButton></Tooltip>
                  </Can>
                  {it.is_active && !it.is_target && (
                    <Can permission="catalogos:eliminar">
                      <Tooltip title="Desactivar"><IconButton size="small" aria-label={`Desactivar ${it.name}`} onClick={() => deactivate(it)}><BlockIcon fontSize="small" /></IconButton></Tooltip>
                    </Can>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {editing && (
        <CatalogDialog name={name} item={editing === "new" ? null : editing} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); qc.invalidateQueries({ queryKey: ["catalogo", name] }); }} />
      )}
    </Box>
  );
}

function CatalogDialog({ name, item, onClose, onSaved }: { name: CatalogName; item: CatalogItem | null; onClose(): void; onSaved(): void }) {
  const fields = FIELDS[name];
  const [form, setForm] = useState<Record<string, string>>(
    Object.fromEntries(fields.map((f) => [f.key, item?.[f.key] === null || item?.[f.key] === undefined ? "" : String(item[f.key])])),
  );
  const [error, setError] = useState<unknown>(null);

  async function save() {
    setError(null);
    const body: Record<string, unknown> = {};
    fields.forEach((f) => {
      const v = form[f.key as string];
      body[f.key as string] = v === "" ? null : f.type === "number" ? Number(v) : v;
    });
    if (body.name === null) return;
    try {
      if (item) await api(`/catalogos/${name}/${item.id}`, { method: "PATCH", body });
      else await api(`/catalogos/${name}`, { method: "POST", body });
      onSaved();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth aria-labelledby="cat-title">
      <DialogTitle id="cat-title">{item ? "Editar" : "Agregar"} · {TITLES[name]}</DialogTitle>
      <DialogContent>
        <ErrorAlert error={error} />
        <Stack spacing={2} sx={{ mt: 1 }}>
          {fields.map((f) => (
            <TextField key={f.key} label={f.label} value={form[f.key as string]} multiline={f.multiline} minRows={f.multiline ? 2 : undefined}
              select={!!f.options} type={f.type} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}>
              {f.options?.map(([v, l]) => <MenuItem key={v} value={v}>{l}</MenuItem>)}
            </TextField>
          ))}
          {name === "variedades" && form.late_blight_susceptibility && !form.source && (
            <Alert severity="warning">Indique la fuente: no se deben registrar datos de susceptibilidad sin respaldo.</Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="contained" onClick={save}
          disabled={!form.name || (name === "variedades" && !!form.late_blight_susceptibility && !form.source)}>Guardar</Button>
      </DialogActions>
    </Dialog>
  );
}

function UbigeoTab() {
  const regions = useRegions();
  const qc = useQueryClient();
  const [dep, setDep] = useState("120000");
  const [prov, setProv] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const provinces = useQuery({ queryKey: ["ubigeo", "provincia", dep], queryFn: () => api<Ubigeo[]>("/catalogos/ubigeo", { query: { level: "provincia", parent: dep } }) });
  const districts = useQuery({ queryKey: ["ubigeo", "distrito", prov], enabled: !!prov, queryFn: () => api<Ubigeo[]>("/catalogos/ubigeo", { query: { level: "distrito", parent: prov } }) });

  async function upload(file: File) {
    setError(null);
    setResult(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api<{ filas_leidas: number; creados: number }>("/catalogos/ubigeo/importar", { method: "POST", form: fd });
      setResult(`Filas leídas: ${r.filas_leidas} · nuevos registros: ${r.creados}`);
      qc.invalidateQueries({ queryKey: ["ubigeo"] });
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Box>
      <Alert severity="info" sx={{ mb: 2 }}>
        Se incluyen los 25 departamentos. Las provincias y distritos se importan desde un CSV con las columnas
        <code> ubigeo</code> (código INEI de 6 dígitos) y <code>nombre</code>. Documente la fuente y la licencia del archivo.
      </Alert>
      <Can permission="catalogos:crear">
        <Button component="label" variant="outlined" sx={{ mb: 2 }}>
          Importar CSV de ubigeo
          <input hidden type="file" accept=".csv,text/csv" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </Button>
      </Can>
      {result && <Alert severity="success" sx={{ mb: 2 }}>{result}</Alert>}
      <ErrorAlert error={error} />
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mb: 2 }}>
        <TextField select label="Departamento" value={dep} onChange={(e) => { setDep(e.target.value); setProv(""); }}>
          {regions.data?.map((r) => <MenuItem key={r.code} value={r.code}>{r.code} · {r.name}</MenuItem>)}
        </TextField>
        <TextField select label="Provincia" value={prov} onChange={(e) => setProv(e.target.value)} disabled={!provinces.data?.length}
          helperText={provinces.data?.length === 0 ? "Sin provincias importadas" : " "}>
          {provinces.data?.map((p) => <MenuItem key={p.code} value={p.code}>{p.code} · {p.name}</MenuItem>)}
        </TextField>
      </Stack>
      {districts.data && (
        <Typography variant="body2">Distritos: {districts.data.map((d) => d.name).join(", ") || "—"}</Typography>
      )}
    </Box>
  );
}
