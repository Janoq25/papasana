import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Button, Card, CardContent, Grid, Stack, TextField, Typography } from "@mui/material";
import { api } from "../../api/client";
import type { Setting } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import { formatDateTime } from "../../utils/format";

export default function SettingsPage() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api<Setting[]>("/settings") });
  const { can } = useAuth();
  const groups = new Map<string, Setting[]>();
  settings.data?.forEach((s) => {
    const g = s.key.split(".")[0];
    groups.set(g, [...(groups.get(g) ?? []), s]);
  });
  const titles: Record<string, string> = {
    seguridad: "Seguridad",
    diagnostico: "Diagnóstico",
    institucion: "Institución",
    aviso: "Avisos",
  };

  return (
    <Box>
      <PageHeader title="Configuración del sistema" subtitle="Parámetros editables sin modificar código. Cada cambio queda en la bitácora." />
      <ErrorAlert error={settings.error} />
      <Stack spacing={2}>
        {[...groups.entries()].map(([g, items]) => (
          <Card key={g} variant="outlined">
            <CardContent>
              <Typography variant="h2" gutterBottom>{titles[g] ?? g}</Typography>
              <Grid container spacing={2}>
                {items.map((s) => (
                  <Grid key={s.key} size={{ xs: 12, md: s.type === "str" ? 12 : 6 }}>
                    <SettingField setting={s} editable={can("configuracion:editar")} />
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </Box>
  );
}

function SettingField({ setting, editable }: { setting: Setting; editable: boolean }) {
  const qc = useQueryClient();
  const { reloadMe } = useAuth();
  const [value, setValue] = useState(String(setting.value));
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const changed = value !== String(setting.value);
  const numeric = setting.type !== "str";

  async function save() {
    setError(null);
    setSaved(false);
    try {
      const v = setting.type === "int" ? parseInt(value, 10) : setting.type === "float" ? parseFloat(value) : value;
      await api(`/settings/${setting.key}`, { method: "PUT", body: { value: v } });
      setSaved(true);
      await qc.invalidateQueries({ queryKey: ["settings"] });
      await reloadMe();
    } catch (err) {
      setError(err);
    }
  }

  const range = numeric && setting.min !== null ? ` (entre ${setting.min} y ${setting.max})` : "";
  return (
    <Box>
      <ErrorAlert error={error} />
      {saved && <Alert severity="success" sx={{ mb: 1 }}>Guardado.</Alert>}
      <Stack direction="row" spacing={1} sx={{ alignItems: "flex-start" }}>
        <TextField
          label={setting.key}
          value={value}
          disabled={!editable}
          type={numeric ? "number" : "text"}
          multiline={!numeric && value.length > 80}
          slotProps={{ htmlInput: numeric ? { min: setting.min ?? undefined, max: setting.max ?? undefined, step: setting.type === "float" ? 0.01 : 1 } : {} }}
          helperText={`${setting.description}${range} · Última modificación: ${formatDateTime(setting.updated_at)}`}
          onChange={(e) => setValue(e.target.value)}
        />
        {editable && (
          <Button variant="outlined" onClick={save} disabled={!changed} sx={{ mt: 0.25 }}>Guardar</Button>
        )}
      </Stack>
    </Box>
  );
}
