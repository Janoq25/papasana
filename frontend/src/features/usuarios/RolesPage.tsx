import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
  Grid,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../../api/client";
import type { PermissionCatalog, Role } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Can } from "../../auth/RequirePermission";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import { SCOPE_LABELS } from "../../utils/format";
import { useRoles } from "./UsersPage";

const ACTION_LABELS: Record<string, string> = {
  ver: "Ver",
  crear: "Crear",
  editar: "Editar",
  eliminar: "Eliminar",
  exportar: "Exportar",
  aprobar: "Aprobar",
};

export default function RolesPage() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const roles = useRoles();
  const catalog = useQuery({ queryKey: ["permission-catalog"], queryFn: () => api<PermissionCatalog>("/roles/catalogo-permisos") });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Set<string>>(new Set());
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Role | "new" | null>(null);

  const selected = roles.data?.find((r) => r.id === selectedId) ?? roles.data?.[0] ?? null;
  useEffect(() => {
    if (selected) setDraft(new Set(selected.permissions));
  }, [selected?.id, selected?.permissions.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = useMemo(
    () => !!selected && (selected.permissions.length !== draft.size || selected.permissions.some((p) => !draft.has(p))),
    [selected, draft],
  );
  const editable = can("usuarios:editar");

  function toggle(key: string) {
    const next = new Set(draft);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setDraft(next);
  }

  async function save() {
    if (!selected) return;
    setError(null);
    try {
      await api(`/roles/${selected.id}/permisos`, { method: "PUT", body: { permissions: [...draft].sort() } });
      setNotice(`Permisos de «${selected.name}» actualizados y registrados en la bitácora.`);
      qc.invalidateQueries({ queryKey: ["roles"] });
    } catch (err) {
      setError(err);
    }
  }

  async function remove(role: Role) {
    if (!window.confirm(`¿Eliminar el rol «${role.name}»?`)) return;
    setError(null);
    try {
      await api(`/roles/${role.id}`, { method: "DELETE" });
      setSelectedId(null);
      setNotice("Rol eliminado.");
      qc.invalidateQueries({ queryKey: ["roles"] });
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Box>
      <PageHeader
        title="Roles y permisos"
        subtitle="Matriz módulo × acción. El backend valida estos permisos en cada endpoint."
        actions={
          <Can permission="usuarios:crear">
            <Button variant="contained" onClick={() => setDialog("new")}>Nuevo rol</Button>
          </Can>
        }
      />
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}
      <ErrorAlert error={error || roles.error || catalog.error} />
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper variant="outlined">
            <List dense aria-label="Roles">
              {roles.data?.map((r) => (
                <ListItemButton key={r.id} selected={selected?.id === r.id} onClick={() => setSelectedId(r.id)}>
                  <ListItemText primary={r.name} secondary={`${r.user_count} usuario(s)${r.is_system ? " · sistema" : ""}`} />
                </ListItemButton>
              ))}
            </List>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 9 }}>
          {selected && catalog.data && (
            <Card variant="outlined">
              <CardContent>
                <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ alignItems: { sm: "center" }, mb: 2 }}>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="h2">{selected.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {selected.description} · Alcance de datos: {SCOPE_LABELS[selected.data_scope]}
                    </Typography>
                  </Box>
                  <Can permission="usuarios:editar">
                    <Button size="small" onClick={() => setDialog(selected)}>Editar datos</Button>
                  </Can>
                  {!selected.is_system && (
                    <Can permission="usuarios:eliminar">
                      <Button size="small" color="error" onClick={() => remove(selected)}>Eliminar</Button>
                    </Can>
                  )}
                </Stack>
                <TableContainer>
                  <Table size="small" aria-label={`Permisos del rol ${selected.name}`}>
                    <TableHead>
                      <TableRow>
                        <TableCell>Módulo</TableCell>
                        {catalog.data.acciones.map((a) => <TableCell key={a} align="center">{ACTION_LABELS[a]}</TableCell>)}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {catalog.data.modulos.map((m) => (
                        <TableRow key={m.code} hover>
                          <TableCell>
                            {m.name}{" "}
                            {m.phase > 1 && <Chip size="small" variant="outlined" label={`F${m.phase}`} sx={{ ml: 0.5 }} />}
                          </TableCell>
                          {catalog.data.acciones.map((a) => {
                            const key = `${m.code}:${a}`;
                            return (
                              <TableCell key={a} align="center" padding="checkbox">
                                <Checkbox checked={draft.has(key)} disabled={!editable} onChange={() => toggle(key)}
                                  slotProps={{ input: { "aria-label": `${m.name}: ${ACTION_LABELS[a]}` } }} />
                              </TableCell>
                            );
                          })}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
                {editable && (
                  <Stack direction="row" spacing={1} sx={{ mt: 2, justifyContent: "flex-end" }}>
                    <Button disabled={!dirty} onClick={() => setDraft(new Set(selected.permissions))}>Descartar</Button>
                    <Button variant="contained" disabled={!dirty} onClick={save}>Guardar permisos</Button>
                  </Stack>
                )}
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>
      {dialog && (
        <RoleDialog role={dialog === "new" ? null : dialog} onClose={() => setDialog(null)}
          onSaved={(r) => { setDialog(null); setSelectedId(r.id); setNotice("Rol guardado."); qc.invalidateQueries({ queryKey: ["roles"] }); }} />
      )}
    </Box>
  );
}

function RoleDialog({ role, onClose, onSaved }: { role: Role | null; onClose(): void; onSaved(r: Role): void }) {
  const [form, setForm] = useState({
    code: role?.code ?? "",
    name: role?.name ?? "",
    description: role?.description ?? "",
    data_scope: role?.data_scope ?? "propio",
  });
  const [error, setError] = useState<unknown>(null);

  async function save() {
    setError(null);
    try {
      const r = role
        ? await api<Role>(`/roles/${role.id}`, { method: "PATCH", body: { name: form.name, description: form.description || null, data_scope: form.data_scope } })
        : await api<Role>("/roles", { method: "POST", body: { ...form, description: form.description || null } });
      onSaved(r);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth aria-labelledby="role-dialog-title">
      <DialogTitle id="role-dialog-title">{role ? "Editar rol" : "Nuevo rol"}</DialogTitle>
      <DialogContent>
        <ErrorAlert error={error} />
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField label="Código" value={form.code} disabled={!!role} helperText="Letras y guion bajo, p. ej. OBSERVADOR_REGIONAL"
            onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} />
          <TextField label="Nombre" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <TextField label="Descripción" multiline minRows={2} value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <TextField select label="Alcance de datos" value={form.data_scope}
            helperText="Qué registros de campo puede ver (se aplica desde la Fase 2)."
            onChange={(e) => setForm({ ...form, data_scope: e.target.value as Role["data_scope"] })}>
            {Object.entries(SCOPE_LABELS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
          </TextField>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="contained" onClick={save} disabled={!form.name || (!role && !form.code)}>Guardar</Button>
      </DialogActions>
    </Dialog>
  );
}
