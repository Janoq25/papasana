import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
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
  Stack,
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
import EditIcon from "@mui/icons-material/Edit";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import MailIcon from "@mui/icons-material/Mail";
import PersonAddIcon from "@mui/icons-material/PersonAdd";
import { api } from "../../api/client";
import type { Page, Role, User } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Can } from "../../auth/RequirePermission";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import { formatDateTime } from "../../utils/format";
import { useRegions } from "../perfil/ProfilePage";

export function useRoles() {
  return useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/roles") });
}

export default function UsersPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [roleId, setRoleId] = useState<string>("");
  const [active, setActive] = useState<string>("");
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const [editing, setEditing] = useState<User | "new" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const roles = useRoles();

  const users = useQuery({
    queryKey: ["users", q, roleId, active, page, size],
    queryFn: () =>
      api<Page<User>>("/users", { query: { q, role_id: roleId, is_active: active, page: page + 1, size } }),
    placeholderData: keepPreviousData,
  });

  const action = useMutation({
    mutationFn: ({ path }: { path: string; msg: string }) => api(path, { method: "POST" }),
    onSuccess: (_, v) => {
      setNotice(v.msg);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });

  return (
    <Box>
      <PageHeader
        title="Usuarios"
        subtitle="Cuentas, roles asignados, estado y bloqueos."
        actions={
          <Can permission="usuarios:crear">
            <Button variant="contained" startIcon={<PersonAddIcon />} onClick={() => setEditing("new")}>
              Nuevo usuario
            </Button>
          </Can>
        }
      />
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}
      <ErrorAlert error={users.error || action.error} />
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField label="Buscar por nombre o correo" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <TextField select label="Rol" value={roleId} onChange={(e) => { setRoleId(e.target.value); setPage(0); }}>
              <MenuItem value="">Todos</MenuItem>
              {roles.data?.map((r) => <MenuItem key={r.id} value={String(r.id)}>{r.name}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <TextField select label="Estado" value={active} onChange={(e) => { setActive(e.target.value); setPage(0); }}>
              <MenuItem value="">Todos</MenuItem>
              <MenuItem value="true">Activos</MenuItem>
              <MenuItem value="false">Inactivos</MenuItem>
            </TextField>
          </Grid>
        </Grid>
      </Paper>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label="Usuarios">
          <TableHead>
            <TableRow>
              <TableCell>Nombre</TableCell>
              <TableCell>Correo</TableCell>
              <TableCell>Rol</TableCell>
              <TableCell>Estado</TableCell>
              <TableCell>Último acceso</TableCell>
              <TableCell align="right">Acciones</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.data?.items.map((u) => (
              <TableRow key={u.id} hover>
                <TableCell>{u.full_name}</TableCell>
                <TableCell>{u.email}</TableCell>
                <TableCell>{u.role.name}</TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5}>
                    <Chip size="small" label={u.is_active ? "Activo" : "Inactivo"} color={u.is_active ? "success" : "default"} />
                    {u.is_locked && <Chip size="small" label="Bloqueado" color="warning" />}
                  </Stack>
                </TableCell>
                <TableCell>{formatDateTime(u.last_login_at)}</TableCell>
                <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                  <Can permission="usuarios:editar">
                    <Tooltip title="Editar">
                      <IconButton size="small" aria-label={`Editar ${u.full_name}`} onClick={() => setEditing(u)}><EditIcon fontSize="small" /></IconButton>
                    </Tooltip>
                    {u.is_locked && (
                      <Tooltip title="Desbloquear">
                        <IconButton size="small" aria-label={`Desbloquear ${u.full_name}`}
                          onClick={() => action.mutate({ path: `/users/${u.id}/unlock`, msg: "Cuenta desbloqueada." })}>
                          <LockOpenIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                    <Tooltip title="Enviar enlace para restablecer contraseña">
                      <IconButton size="small" aria-label={`Enviar enlace a ${u.full_name}`}
                        onClick={() => action.mutate({ path: `/users/${u.id}/send-reset`, msg: `Enlace enviado a ${u.email}.` })}>
                        <MailIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Can>
                </TableCell>
              </TableRow>
            ))}
            {users.data?.items.length === 0 && (
              <TableRow><TableCell colSpan={6} align="center">Sin resultados</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination component="div" count={users.data?.total ?? 0} page={page} rowsPerPage={size}
          onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(e) => { setSize(Number(e.target.value)); setPage(0); }}
          rowsPerPageOptions={[10, 20, 50]} />
      </TableContainer>
      {editing && (
        <UserDialog user={editing === "new" ? null : editing} roles={roles.data ?? []} onClose={() => setEditing(null)}
          onSaved={(msg) => { setEditing(null); setNotice(msg); qc.invalidateQueries({ queryKey: ["users"] }); }} />
      )}
    </Box>
  );
}

function UserDialog({ user, roles, onClose, onSaved }: { user: User | null; roles: Role[]; onClose(): void; onSaved(msg: string): void }) {
  const { user: me, can } = useAuth();
  const regions = useRegions();
  const [form, setForm] = useState({
    email: user?.email ?? "",
    full_name: user?.full_name ?? "",
    password: "",
    role_id: user ? String(user.role.id) : "",
    institution: user?.institution ?? "",
    phone: user?.phone ?? "",
    region_code: user?.region_code ?? "",
    is_active: user?.is_active ?? true,
  });
  const [error, setError] = useState<unknown>(null);
  const isSelf = user?.id === me?.id;

  async function save() {
    setError(null);
    const common = {
      full_name: form.full_name,
      institution: form.institution || null,
      phone: form.phone || null,
      region_code: form.region_code || null,
    };
    try {
      if (user) {
        const body: Record<string, unknown> = { ...common };
        if (!isSelf) body.role_id = Number(form.role_id);
        if (!isSelf && form.is_active !== user.is_active) body.is_active = form.is_active;
        await api(`/users/${user.id}`, { method: "PATCH", body });
        onSaved("Usuario actualizado.");
      } else {
        await api("/users", { method: "POST", body: { ...common, email: form.email, password: form.password, role_id: Number(form.role_id) } });
        onSaved("Usuario creado.");
      }
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth aria-labelledby="user-dialog-title">
      <DialogTitle id="user-dialog-title">{user ? "Editar usuario" : "Nuevo usuario"}</DialogTitle>
      <DialogContent>
        <ErrorAlert error={error} />
        <Grid container spacing={2} sx={{ mt: 0.5 }}>
          <Grid size={12}>
            <TextField label="Correo electrónico" type="email" value={form.email} disabled={!!user} required
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Grid>
          <Grid size={12}>
            <TextField label="Nombre completo" value={form.full_name} required onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </Grid>
          {!user && (
            <Grid size={12}>
              <TextField label="Contraseña inicial" type="password" autoComplete="new-password" value={form.password} required
                helperText="El usuario podrá cambiarla desde su perfil." onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </Grid>
          )}
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField select label="Rol" value={form.role_id} required disabled={isSelf}
              helperText={isSelf ? "No puede cambiar su propio rol." : " "} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
              {roles.map((r) => <MenuItem key={r.id} value={String(r.id)}>{r.name}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField select label="Región" value={form.region_code} onChange={(e) => setForm({ ...form, region_code: e.target.value })}>
              <MenuItem value="">Sin región</MenuItem>
              {regions.data?.map((r) => <MenuItem key={r.code} value={r.code}>{r.name}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField label="Institución" value={form.institution} onChange={(e) => setForm({ ...form, institution: e.target.value })} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField label="Teléfono" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </Grid>
          {user && !isSelf && can("usuarios:eliminar") && (
            <Grid size={12}>
              <TextField select label="Estado de la cuenta" value={form.is_active ? "1" : "0"}
                helperText="Desactivar cierra todas las sesiones del usuario. No se borran sus registros."
                onChange={(e) => setForm({ ...form, is_active: e.target.value === "1" })}>
                <MenuItem value="1">Activa</MenuItem>
                <MenuItem value="0">Desactivada</MenuItem>
              </TextField>
            </Grid>
          )}
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="contained" onClick={save} disabled={!form.full_name || !form.role_id || (!user && (!form.email || !form.password))}>
          Guardar
        </Button>
      </DialogActions>
    </Dialog>
  );
}
