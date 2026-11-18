import { useState, type FormEvent } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
import { Alert, Box, Button, Link, Stack, TextField } from "@mui/material";
import { api } from "../../api/client";
import ErrorAlert from "../../components/ErrorAlert";
import { AuthCard } from "./LoginPage";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const r = await api<{ message: string }>("/auth/forgot-password", { method: "POST", body: { email: email.trim() } });
      setDone(r.message);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <AuthCard title="Recuperar contraseña">
      {done ? (
        <Alert severity="success">{done}</Alert>
      ) : (
        <Box component="form" onSubmit={onSubmit}>
          <ErrorAlert error={error} />
          <Stack spacing={2}>
            <TextField label="Correo electrónico" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
            <Button type="submit" variant="contained" disabled={!email}>
              Enviar enlace
            </Button>
          </Stack>
        </Box>
      )}
      <Link component={RouterLink} to="/login" variant="body2" sx={{ display: "block", mt: 2 }}>
        Volver al inicio de sesión
      </Link>
    </AuthCard>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const mismatch = confirm.length > 0 && password !== confirm;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/auth/reset-password", { method: "POST", body: { token, new_password: password } });
      setDone(true);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <AuthCard title="Nueva contraseña">
      {!token && <Alert severity="error">El enlace no es válido.</Alert>}
      {done ? (
        <Alert severity="success">Contraseña actualizada. Ya puede iniciar sesión.</Alert>
      ) : (
        token && (
          <Box component="form" onSubmit={onSubmit}>
            <ErrorAlert error={error} />
            <Stack spacing={2}>
              <TextField label="Nueva contraseña" type="password" autoComplete="new-password" value={password}
                onChange={(e) => setPassword(e.target.value)} required
                helperText="Mínimo 10 caracteres, con mayúscula, minúscula y número." />
              <TextField label="Confirmar contraseña" type="password" autoComplete="new-password" value={confirm}
                onChange={(e) => setConfirm(e.target.value)} required error={mismatch}
                helperText={mismatch ? "Las contraseñas no coinciden." : " "} />
              <Button type="submit" variant="contained" disabled={!password || mismatch}>
                Guardar contraseña
              </Button>
            </Stack>
          </Box>
        )
      )}
      <Link component={RouterLink} to="/login" variant="body2" sx={{ display: "block", mt: 2 }}>
        Ir al inicio de sesión
      </Link>
    </AuthCard>
  );
}
