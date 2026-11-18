import { useState } from "react";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Grid,
  LinearProgress,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import type { Diagnosis } from "../api/types";
import { useAuthedObjectUrl } from "../api/useAuthedObjectUrl";
import {
  CATEGORY_COLOR,
  CATEGORY_LABEL,
  CLASS_LABEL,
  GPS_LABEL,
  percent,
  sortedProbabilities,
  STATUS_LABEL,
} from "../utils/diagnosis";
import { formatDateTime } from "../utils/format";

/** Franja obligatoria cuando el modelo no está validado (restricción científica §6). */
export function DemoBanner({ diagnosis }: { diagnosis: Pick<Diagnosis, "model"> }) {
  if (!diagnosis.model.is_demo) return null;
  return (
    <Alert severity="error" variant="filled" sx={{ mb: 2 }} role="alert">
      <strong>DEMO / no validado.</strong> Este resultado proviene de un modelo de demostración sin entrenar. No tiene
      valor diagnóstico.
    </Alert>
  );
}

function ImageView({ diagnosis }: { diagnosis: Diagnosis }) {
  const [view, setView] = useState<"original" | "gradcam">(diagnosis.has_gradcam ? "gradcam" : "original");
  const original = useAuthedObjectUrl(`/diagnosticos/${diagnosis.id}/imagen`);
  const gradcam = useAuthedObjectUrl(diagnosis.has_gradcam ? `/diagnosticos/${diagnosis.id}/gradcam` : null);
  const current = view === "gradcam" ? gradcam : original;
  return (
    <Box>
      {diagnosis.has_gradcam && (
        <ToggleButtonGroup size="small" exclusive value={view} onChange={(_, v) => v && setView(v)}
          aria-label="Vista de la imagen" sx={{ mb: 1 }}>
          <ToggleButton value="gradcam">Mapa Grad-CAM</ToggleButton>
          <ToggleButton value="original">Foto original</ToggleButton>
        </ToggleButtonGroup>
      )}
      <Box sx={{ position: "relative", bgcolor: "#eef1ea", borderRadius: 2, minHeight: 220, display: "grid", placeItems: "center", overflow: "hidden" }}>
        {current.url ? (
          <Box component="img" src={current.url} sx={{ width: "100%", height: "auto", display: "block" }}
            alt={view === "gradcam" ? "Mapa Grad-CAM superpuesto a la hoja: las zonas rojas influyeron más en la predicción"
              : `Fotografía original ${diagnosis.image.original_filename ?? ""}`} />
        ) : current.error ? (
          <Typography variant="body2" color="text.secondary">No se pudo cargar la imagen.</Typography>
        ) : (
          <CircularProgress size={28} aria-label="Cargando imagen" />
        )}
      </Box>
      {view === "gradcam" && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
          Rojo = zonas que más influyeron en la predicción; azul = poca influencia. Con el modelo DEMO el mapa no es
          interpretable agronómicamente.
        </Typography>
      )}
    </Box>
  );
}

export default function DiagnosisResult({ diagnosis }: { diagnosis: Diagnosis }) {
  const d = diagnosis;
  const img = d.image;
  return (
    <Box>
      <DemoBanner diagnosis={d} />
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          <ImageView diagnosis={d} />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1, mb: 2 }}>
            <Chip label={CATEGORY_LABEL[d.category]} color={CATEGORY_COLOR[d.category]} sx={{ fontWeight: 600 }} />
            <Chip label={STATUS_LABEL[d.status]} variant="outlined" />
            {d.requires_review && <Chip label="Requiere revisión" color="warning" variant="outlined" />}
          </Stack>
          <Typography variant="body2" color="text.secondary">Confianza</Typography>
          <Typography variant="h2" component="p" sx={{ mb: 0.5 }}>{percent(d.confidence)}</Typography>
          <Typography variant="caption" color="text.secondary">
            Umbral de revisión: {percent(d.threshold_used)} · las etiquetas describen síntomas, no confirman el patógeno
          </Typography>

          <Box sx={{ mt: 2 }} aria-label="Probabilidades por clase">
            {sortedProbabilities(d.probabilities).map(([cls, p]) => (
              <Box key={cls} sx={{ mb: 1 }}>
                <Stack direction="row" sx={{ justifyContent: "space-between" }}>
                  <Typography variant="body2">{CLASS_LABEL[cls] ?? cls}</Typography>
                  <Typography variant="body2">{percent(p)}</Typography>
                </Stack>
                <LinearProgress variant="determinate" value={p * 100} aria-label={`${CLASS_LABEL[cls] ?? cls}: ${percent(p)}`}
                  sx={{ height: 8, borderRadius: 4 }} />
              </Box>
            ))}
          </Box>

          <Box component="dl" sx={{ mt: 2, display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 2, rowGap: 0.5, "& dt": { color: "text.secondary" }, "& dd": { m: 0 } }}>
            <Typography component="dt" variant="body2">Parcela</Typography>
            <Typography component="dd" variant="body2">{d.parcel.code} · {d.parcel.name}</Typography>
            <Typography component="dt" variant="body2">Fecha</Typography>
            <Typography component="dd" variant="body2">{formatDateTime(d.created_at)}</Typography>
            <Typography component="dt" variant="body2">Captura</Typography>
            <Typography component="dd" variant="body2">{formatDateTime(img.captured_at)}</Typography>
            <Typography component="dt" variant="body2">Ubicación</Typography>
            <Typography component="dd" variant="body2">
              {GPS_LABEL[img.gps_source]}
              {img.location && ` (${img.location.lat.toFixed(5)}, ${img.location.lon.toFixed(5)})`}
              {img.inside_parcel === true && " · dentro de la parcela"}
              {img.inside_parcel === false && " · FUERA de la parcela"}
            </Typography>
            <Typography component="dt" variant="body2">Modelo</Typography>
            <Typography component="dd" variant="body2">{d.model.display_name}</Typography>
            {d.inference_ms !== null && (
              <>
                <Typography component="dt" variant="body2">Inferencia</Typography>
                <Typography component="dd" variant="body2">{d.inference_ms} ms</Typography>
              </>
            )}
          </Box>

          {img.duplicate_of_id && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Posible foto casi duplicada de una imagen anterior (distancia {img.duplicate_distance}). Se excluirá de los
              datos de reentrenamiento si se confirma.
            </Alert>
          )}
          {img.inside_parcel === false && (
            <Alert severity="warning" sx={{ mt: 2 }}>La ubicación de la foto está fuera del polígono de la parcela.</Alert>
          )}
          {d.status === "anulado" && <Alert severity="error" sx={{ mt: 2 }}>Anulado: {d.void_reason}</Alert>}
          {d.reviews.map((r) => (
            <Alert key={r.id} severity={r.decision === "confirma" ? "success" : "info"} sx={{ mt: 2 }}>
              <strong>Validación del especialista:</strong> {r.final_label_name}
              {r.differential && ` (${r.differential})`}
              {r.evidence && ` · evidencia: ${r.evidence}`}
              {r.notes && ` · ${r.notes}`} — {formatDateTime(r.created_at)}
            </Alert>
          ))}
        </Grid>
      </Grid>
      <Alert severity="warning" variant="outlined" sx={{ mt: 2 }}>{d.disclaimer}</Alert>
    </Box>
  );
}
