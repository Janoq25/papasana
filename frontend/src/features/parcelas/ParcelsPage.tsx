import { useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
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
  Tooltip,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import GroupAddIcon from "@mui/icons-material/GroupAdd";
import { api } from "../../api/client";
import type { CatalogItem, Page, Parcel, ParcelFeatureCollection, Producer } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Can } from "../../auth/RequirePermission";
import ErrorAlert from "../../components/ErrorAlert";
import { ParcelsMap, PolygonEditor } from "../../components/maps";
import PageHeader from "../../components/PageHeader";
import { fromPolygon, selfIntersects, toPolygon, type LatLng } from "../../utils/geo";
import { useRegions } from "../perfil/ProfilePage";

export function useCatalog(name: "variedades" | "estadios" | "enfermedades") {
  return useQuery({ queryKey: ["catalogo", name], queryFn: () => api<CatalogItem[]>(`/catalogos/${name}`), staleTime: 300_000 });
}

export function useParcelGeojson() {
  return useQuery({ queryKey: ["parcelas-geojson"], queryFn: () => api<ParcelFeatureCollection>("/parcelas/geojson") });
}

export default function ParcelsPage() {
  const qc = useQueryClient();
  const regions = useRegions();
  const varieties = useCatalog("variedades");
  const [q, setQ] = useState("");
  const [region, setRegion] = useState("");
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const [selected, setSelected] = useState<number | null>(null);
  const [editing, setEditing] = useState<Parcel | "new" | null>(null);
  const [assigning, setAssigning] = useState<Parcel | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ["parcelas", q, region, page, size],
    queryFn: () => api<Page<Parcel>>("/parcelas", { query: { q, region, page: page + 1, size } }),
    placeholderData: keepPreviousData,
  });
  const geo = useParcelGeojson();
  const regionName = (code: string) => regions.data?.find((r) => r.code === `${code.slice(0, 2)}0000`)?.name ?? code;

  async function openEdit(id: number) {
    setEditing(await api<Parcel>(`/parcelas/${id}`));
  }

  function refresh(msg: string) {
    setNotice(msg);
    qc.invalidateQueries({ queryKey: ["parcelas"] });
    qc.invalidateQueries({ queryKey: ["parcelas-geojson"] });
  }

  return (
    <Box>
      <PageHeader
        title="Parcelas"
        subtitle="Parcelas georreferenciadas visibles según su rol (todas, su región o las asignadas)."
        actions={
          <Can permission="parcelas:crear">
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setEditing("new")}>Nueva parcela</Button>
          </Can>
        }
      />
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}
      <ErrorAlert error={list.error || geo.error} />
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 6 }}>
          <ParcelsMap data={geo.data} selectedId={selected} onSelect={setSelected} />
        </Grid>
        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 7 }}>
                <TextField label="Buscar por nombre o código" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
              </Grid>
              <Grid size={{ xs: 12, sm: 5 }}>
                <TextField select label="Región" value={region} onChange={(e) => { setRegion(e.target.value); setPage(0); }}>
                  <MenuItem value="">Todas</MenuItem>
                  {regions.data?.map((r) => <MenuItem key={r.code} value={r.code}>{r.name}</MenuItem>)}
                </TextField>
              </Grid>
            </Grid>
          </Paper>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small" aria-label="Parcelas">
              <TableHead>
                <TableRow>
                  <TableCell>Código</TableCell>
                  <TableCell>Nombre</TableCell>
                  <TableCell>Región</TableCell>
                  <TableCell>Variedad</TableCell>
                  <TableCell align="right">Área (ha)</TableCell>
                  <TableCell align="right">Acciones</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {list.data?.items.map((p) => (
                  <TableRow key={p.id} hover selected={p.id === selected} onClick={() => setSelected(p.id)} sx={{ cursor: "pointer" }}>
                    <TableCell>{p.code}</TableCell>
                    <TableCell>
                      {p.name}
                      {p.stage && <Chip size="small" label={p.stage.name} variant="outlined" sx={{ ml: 1 }} />}
                    </TableCell>
                    <TableCell>{regionName(p.region_code)}</TableCell>
                    <TableCell>{p.variety?.name ?? "—"}</TableCell>
                    <TableCell align="right">{p.area_ha.toFixed(2)}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                      <Can permission="parcelas:editar">
                        <Tooltip title="Editar">
                          <IconButton size="small" aria-label={`Editar ${p.name}`} onClick={(e) => { e.stopPropagation(); void openEdit(p.id); }}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Asignar técnicos">
                          <IconButton size="small" aria-label={`Asignar técnicos a ${p.name}`} onClick={(e) => { e.stopPropagation(); setAssigning(p); }}>
                            <GroupAddIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Can>
                    </TableCell>
                  </TableRow>
                ))}
                {list.data?.items.length === 0 && <TableRow><TableCell colSpan={6} align="center">Sin parcelas en su alcance</TableCell></TableRow>}
              </TableBody>
            </Table>
            <TablePagination component="div" count={list.data?.total ?? 0} page={page} rowsPerPage={size}
              onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(e) => { setSize(Number(e.target.value)); setPage(0); }}
              rowsPerPageOptions={[10, 20, 50]} />
          </TableContainer>
        </Grid>
      </Grid>
      {editing && (
        <ParcelDialog parcel={editing === "new" ? null : editing} context={geo.data} varieties={varieties.data ?? []}
          onClose={() => setEditing(null)} onSaved={(msg) => { setEditing(null); refresh(msg); }} />
      )}
      {assigning && (
        <AssignDialog parcel={assigning} onClose={() => setAssigning(null)}
          onSaved={() => { setAssigning(null); refresh("Asignaciones actualizadas."); }} />
      )}
    </Box>
  );
}

function ParcelDialog({ parcel, context, varieties, onClose, onSaved }: {
  parcel: Parcel | null; context?: ParcelFeatureCollection; varieties: CatalogItem[]; onClose(): void; onSaved(msg: string): void;
}) {
  const { user, can } = useAuth();
  const regions = useRegions();
  const stages = useCatalog("estadios");
  const qc = useQueryClient();
  const producers = useQuery({ queryKey: ["productores"], queryFn: () => api<Producer[]>("/productores") });
  const [vertices, setVertices] = useState<LatLng[]>(fromPolygon(parcel?.geometry));
  const [form, setForm] = useState({
    name: parcel?.name ?? "",
    region_code: parcel ? `${parcel.region_code.slice(0, 2)}0000` : user?.region_code ?? "",
    producer_id: parcel?.producer?.id ?? null as number | null,
    variety_id: parcel?.variety?.id ? String(parcel.variety.id) : "",
    phenological_stage_id: parcel?.stage?.id ? String(parcel.stage.id) : "",
    sowing_date: parcel?.sowing_date ?? "",
    altitude_m: parcel?.altitude_m ? String(parcel.altitude_m) : "",
    notes: parcel?.notes ?? "",
    is_active: parcel?.is_active ?? true,
  });
  const [newProducer, setNewProducer] = useState("");
  const [error, setError] = useState<unknown>(null);
  const geometry = toPolygon(vertices);
  const invalid = selfIntersects(vertices);
  const geometryChanged = JSON.stringify(vertices) !== JSON.stringify(fromPolygon(parcel?.geometry));

  async function addProducer() {
    setError(null);
    try {
      const p = await api<Producer>("/productores", { method: "POST", body: { name: newProducer, region_code: form.region_code || null } });
      await qc.invalidateQueries({ queryKey: ["productores"] });
      setForm({ ...form, producer_id: p.id });
      setNewProducer("");
    } catch (err) {
      setError(err);
    }
  }

  async function save() {
    setError(null);
    const body: Record<string, unknown> = {
      name: form.name,
      region_code: form.region_code,
      producer_id: form.producer_id,
      variety_id: form.variety_id ? Number(form.variety_id) : null,
      phenological_stage_id: form.phenological_stage_id ? Number(form.phenological_stage_id) : null,
      sowing_date: form.sowing_date || null,
      altitude_m: form.altitude_m ? Number(form.altitude_m) : null,
      notes: form.notes || null,
    };
    try {
      if (parcel) {
        if (geometryChanged) body.geometry = geometry;
        if (form.is_active !== parcel.is_active) body.is_active = form.is_active;
        await api(`/parcelas/${parcel.id}`, { method: "PATCH", body });
        onSaved("Parcela actualizada.");
      } else {
        await api("/parcelas", { method: "POST", body: { ...body, geometry } });
        onSaved("Parcela registrada.");
      }
    } catch (err) {
      setError(err);
    }
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  return (
    <Dialog open onClose={onClose} maxWidth="lg" fullWidth aria-labelledby="parcel-dialog-title">
      <DialogTitle id="parcel-dialog-title">{parcel ? `Editar parcela ${parcel.code}` : "Nueva parcela"}</DialogTitle>
      <DialogContent>
        <ErrorAlert error={error} />
        <Grid container spacing={2} sx={{ mt: 0.5 }}>
          <Grid size={{ xs: 12, md: 7 }}>
            <PolygonEditor vertices={vertices} onChange={setVertices} context={context} />
          </Grid>
          <Grid size={{ xs: 12, md: 5 }}>
            <Grid container spacing={2}>
              <Grid size={12}><TextField label="Nombre" value={form.name} onChange={set("name")} required /></Grid>
              <Grid size={12}>
                <TextField select label="Región (departamento)" value={form.region_code} onChange={set("region_code")} required
                  disabled={user?.role.data_scope === "region"} helperText={user?.role.data_scope === "region" ? "Solo puede registrar parcelas de su región." : " "}>
                  {regions.data?.map((r) => <MenuItem key={r.code} value={r.code}>{r.name}</MenuItem>)}
                </TextField>
              </Grid>
              <Grid size={12}>
                <Autocomplete
                  options={producers.data ?? []}
                  getOptionLabel={(p) => p.name}
                  value={producers.data?.find((p) => p.id === form.producer_id) ?? null}
                  onChange={(_, v) => setForm({ ...form, producer_id: v?.id ?? null })}
                  renderInput={(params) => <TextField {...params} label="Productor" />}
                />
              </Grid>
              {can("parcelas:crear") && (
                <Grid size={12} sx={{ display: "flex", gap: 1 }}>
                  <TextField label="Registrar nuevo productor" value={newProducer} onChange={(e) => setNewProducer(e.target.value)} />
                  <Button onClick={addProducer} disabled={newProducer.trim().length < 2}>Agregar</Button>
                </Grid>
              )}
              <Grid size={6}>
                <TextField select label="Variedad" value={form.variety_id} onChange={set("variety_id")}>
                  <MenuItem value="">Sin especificar</MenuItem>
                  {varieties.map((v) => <MenuItem key={v.id} value={String(v.id)}>{v.name}</MenuItem>)}
                </TextField>
              </Grid>
              <Grid size={6}>
                <TextField select label="Estadio fenológico" value={form.phenological_stage_id} onChange={set("phenological_stage_id")}>
                  <MenuItem value="">Sin especificar</MenuItem>
                  {stages.data?.map((s) => <MenuItem key={s.id} value={String(s.id)}>{s.name}</MenuItem>)}
                </TextField>
              </Grid>
              <Grid size={6}>
                <TextField label="Fecha de siembra" type="date" value={form.sowing_date} onChange={set("sowing_date")}
                  slotProps={{ inputLabel: { shrink: true } }} />
              </Grid>
              <Grid size={6}>
                <TextField label="Altitud (m s. n. m.)" type="number" value={form.altitude_m} onChange={set("altitude_m")}
                  slotProps={{ htmlInput: { min: 0, max: 5500 } }} />
              </Grid>
              <Grid size={12}><TextField label="Notas" value={form.notes} onChange={set("notes")} multiline minRows={2} /></Grid>
              {parcel && can("parcelas:eliminar") && (
                <Grid size={12}>
                  <TextField select label="Estado" value={form.is_active ? "1" : "0"} onChange={(e) => setForm({ ...form, is_active: e.target.value === "1" })}
                    helperText="Desactivar no borra la parcela ni sus diagnósticos.">
                    <MenuItem value="1">Activa</MenuItem>
                    <MenuItem value="0">Desactivada</MenuItem>
                  </TextField>
                </Grid>
              )}
            </Grid>
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="contained" onClick={save} disabled={!form.name || !form.region_code || !geometry || invalid}>Guardar</Button>
      </DialogActions>
    </Dialog>
  );
}

function AssignDialog({ parcel, onClose, onSaved }: { parcel: Parcel; onClose(): void; onSaved(): void }) {
  const users = useQuery({
    queryKey: ["asignables"],
    queryFn: () => api<{ id: string; full_name: string; role_name: string }[]>("/parcelas/asignables"),
  });
  const [selected, setSelected] = useState<string[]>(parcel.assignees);
  const [error, setError] = useState<unknown>(null);

  async function save() {
    setError(null);
    try {
      await api(`/parcelas/${parcel.id}/asignaciones`, { method: "PUT", body: { user_ids: selected } });
      onSaved();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth aria-labelledby="assign-title">
      <DialogTitle id="assign-title">Técnicos asignados · {parcel.code}</DialogTitle>
      <DialogContent>
        <ErrorAlert error={error || users.error} />
        <Autocomplete
          multiple
          sx={{ mt: 1 }}
          options={users.data ?? []}
          getOptionLabel={(u) => `${u.full_name} (${u.role_name})`}
          value={(users.data ?? []).filter((u) => selected.includes(u.id))}
          onChange={(_, v) => setSelected(v.map((u) => u.id))}
          renderInput={(params) => <TextField {...params} label="Usuarios" helperText="Los técnicos solo ven y diagnostican sus parcelas asignadas." />}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="contained" onClick={save}>Guardar</Button>
      </DialogActions>
    </Dialog>
  );
}
