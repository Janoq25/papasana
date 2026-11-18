import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Card, CardContent, Chip, Grid, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { Ubigeo } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import UserAvatar from "../../components/UserAvatar";
import { formatDateTime, SCOPE_LABELS } from "../../utils/format";

export function useRegions() {
  return useQuery({ queryKey: ["ubigeo", "departamento"], queryFn: () => api<Ubigeo[]>("/catalogos/ubigeo"), staleTime: 3_600_000 });
}

export default function ProfilePage() {
  const { user, reloadMe, photoVersion, bumpPhoto } = useAuth();
  const regions = useRegions();
  const [form, setForm] = useState({ full_name: "", institution: "", phone: "", region_code: "" });
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (user)
      setForm({
        full_name: user.full_name,
        institution: user.institution ?? "",
        phone: user.phone ?? "",
        region_code: user.region_code ?? "",
      });
  }, [user]);

  if (!user) return null;

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(null);
    try {
      await api("/users/me", {
        method: "PATCH",
        body: { ...form, institution: form.institution || null, phone: form.phone || null, region_code: form.region_code || null },
      });
      await reloadMe();
      setSaved("Perfil actualizado.");
    } catch (err) {
      setError(err);
    }
  }

  async function uploadPhoto(file: File) {
    setError(null);
    setSaved(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api("/users/me/photo", { method: "POST", form: fd });
      await reloadMe();
      bumpPhoto();
      setSaved("Foto actualizada.");
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Box>
      <PageHeader title="Mi perfil" subtitle="Datos personales, región asignada y seguridad de la cuenta." />
      {saved && <Alert severity="success" sx={{ mb: 2 }}>{saved}</Alert>}
      <ErrorAlert error={error} />
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card variant="outlined">
            <CardContent sx={{ textAlign: "center" }}>
              <UserAvatar userId={user.id} name={user.full_name} hasPhoto={user.has_photo} version={photoVersion}
                sx={{ width: 96, height: 96, mx: "auto", mb: 2, fontSize: 32 }} />
              <Typography variant="h3">{user.full_name}</Typography>
              <Typography variant="body2" color="text.secondary">{user.email}</Typography>
              <Stack direction="row" spacing={1} sx={{ justifyContent: "center", my: 2 }}>
                <Chip label={user.role.name} color="primary" size="small" />
                <Chip label={SCOPE_LABELS[user.role.data_scope]} size="small" variant="outlined" />
              </Stack>
              <Button component="label" variant="outlined" size="small">
                Cambiar foto
                <input hidden type="file" accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => e.target.files?.[0] && uploadPhoto(e.target.files[0])} />
              </Button>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                JPEG, PNG o WebP · máx. 2 MB · se eliminan los metadatos de ubicación
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>
                Último acceso: {formatDateTime(user.last_login_at)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 8 }}>
          <Stack spacing={3}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h2" gutterBottom>Datos personales</Typography>
                <Box component="form" onSubmit={saveProfile}>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <TextField label="Nombre completo" value={form.full_name} required
                        onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <TextField label="Institución" value={form.institution}
                        onChange={(e) => setForm({ ...form, institution: e.target.value })} />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <TextField label="Teléfono" value={form.phone} inputMode="tel"
                        onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      <TextField select label="Región asignada" value={form.region_code}
                        onChange={(e) => setForm({ ...form, region_code: e.target.value })}>
                        <MenuItem value="">Sin región</MenuItem>
                        {regions.data?.map((r) => <MenuItem key={r.code} value={r.code}>{r.name}</MenuItem>)}
                      </TextField>
                    </Grid>
                  </Grid>
                  <Button type="submit" variant="contained" sx={{ mt: 2 }}>Guardar cambios</Button>
                </Box>
              </CardContent>
            </Card>
            <ChangePasswordCard minLength={user.session_settings.longitud_minima_contrasena} />
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
}

function ChangePasswordCard({ minLength }: { minLength: number }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const mismatch = confirm.length > 0 && next !== confirm;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMsg(null);
    try {
      const r = await api<{ message: string }>("/auth/change-password", {
        method: "POST",
        body: { current_password: current, new_password: next },
      });
      setMsg(r.message);
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h2" gutterBottom>Cambiar contraseña</Typography>
        {msg && <Alert severity="success" sx={{ mb: 2 }}>{msg}</Alert>}
        <ErrorAlert error={error} />
        <Box component="form" onSubmit={onSubmit}>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 4 }}>
              <TextField label="Contraseña actual" type="password" autoComplete="current-password" value={current}
                onChange={(e) => setCurrent(e.target.value)} required />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <TextField label="Nueva contraseña" type="password" autoComplete="new-password" value={next}
                onChange={(e) => setNext(e.target.value)} required
                helperText={`Mínimo ${minLength} caracteres, con mayúscula, minúscula y número.`} />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <TextField label="Confirmar" type="password" autoComplete="new-password" value={confirm}
                onChange={(e) => setConfirm(e.target.value)} required error={mismatch}
                helperText={mismatch ? "No coincide." : " "} />
            </Grid>
          </Grid>
          <Button type="submit" variant="contained" disabled={!current || !next || mismatch}>Actualizar contraseña</Button>
        </Box>
      </CardContent>
    </Card>
  );
}
