import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { Alert, Box, Button, Card, CardContent, Link, Stack, TextField, Typography } from "@mui/material";
import { useAuth } from "../../auth/AuthContext";
import { homePath } from "../../app/modules";
import ErrorAlert from "../../components/ErrorAlert";

const REASON_MESSAGES = {
  inactividad: "Su sesión se cerró por inactividad.",
  expirada: "Su sesión expiró. Inicie sesión nuevamente.",
  logout: "Sesión cerrada correctamente.",
} as const;

export function AuthCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", p: 2, bgcolor: "background.default" }}>
      <Card sx={{ width: "100%", maxWidth: 420 }} variant="outlined">
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h6" component="p" sx={{ color: "primary.main", fontWeight: 700 }}>
            PapaSana AP-01
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Detección por síntomas del tizón tardío de la papa
          </Typography>
          <Typography variant="h1" sx={{ fontSize: "1.4rem", mb: 2 }}>
            {title}
          </Typography>
          {children}
        </CardContent>
      </Card>
    </Box>
  );
}

export default function LoginPage() {
  const { login, lastLogoutReason } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const user = await login(email.trim(), password);
      navigate(homePath(user.permissions), { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthCard title="Iniciar sesión">
      {lastLogoutReason && !error && (
        <Alert severity={lastLogoutReason === "logout" ? "success" : "info"} sx={{ mb: 2 }}>
          {REASON_MESSAGES[lastLogoutReason]}
        </Alert>
      )}
      <ErrorAlert error={error} />
      <Box component="form" onSubmit={onSubmit} noValidate>
        <Stack spacing={2}>
          <TextField label="Correo electrónico" type="email" autoComplete="username" value={email}
            onChange={(e) => setEmail(e.target.value)} required autoFocus />
          <TextField label="Contraseña" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
          <Button type="submit" variant="contained" size="large" disabled={loading || !email || !password}>
            {loading ? "Ingresando…" : "Ingresar"}
          </Button>
          <Link component={RouterLink} to="/recuperar" variant="body2">
            ¿Olvidó su contraseña?
          </Link>
        </Stack>
      </Box>
      <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 3 }}>
        Herramienta de apoyo a la decisión para investigación. No reemplaza el diagnóstico de un profesional.
      </Typography>
    </AuthCard>
  );
}
