import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  Link,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../../api/client";
import type { LabModelDetail, SplitEvaluation } from "../../api/types";
import ErrorAlert from "../../components/ErrorAlert";
import { CLASS_LABEL } from "../../utils/diagnosis";
import { fmtMetric, SPLIT_LABEL, STAGE_LABEL } from "./labUtils";

const CLASS_HEX: Record<string, string> = {
  sano: "#2e6b30",
  sintomas_compatibles_tizon_tardio: "#b3261e",
  otra_enfermedad_foliar: "#b07000",
};

function SummaryTable({ ev }: { ev: Record<string, SplitEvaluation> }) {
  const rows: [string, keyof SplitEvaluation][] = [
    ["Imágenes", "n"], ["Accuracy", "accuracy"], ["Macro-F1", "macro_f1"], ["MCC", "mcc"],
    ["Sensibilidad (macro)", "macro_sensitivity"], ["Especificidad (macro)", "macro_specificity"],
    ["AUC-ROC (macro)", "macro_auc_roc"], ["AUC-PR (macro)", "macro_auc_pr"],
  ];
  const splits = Object.keys(ev);
  return (
    <TableContainer>
      <Table size="small" aria-label="Métricas por partición">
        <TableHead><TableRow>
          <TableCell>Métrica</TableCell>
          {splits.map((s) => <TableCell key={s} align="right">{SPLIT_LABEL(s)}</TableCell>)}
        </TableRow></TableHead>
        <TableBody>
          {rows.map(([label, key]) => (
            <TableRow key={key}>
              <TableCell>{label}</TableCell>
              {splits.map((s) => (
                <TableCell key={s} align="right">
                  {key === "n" ? ev[s].n : fmtMetric(ev[s][key] as number | null)}
                </TableCell>
              ))}
            </TableRow>
          ))}
          <TableRow>
            <TableCell>ECE (antes → después de calibrar)</TableCell>
            {splits.map((s) => {
              const c = ev[s].calibration;
              return <TableCell key={s} align="right">{c ? `${fmtMetric(c.before.ece)} → ${fmtMetric(c.after.ece)}` : "—"}</TableCell>;
            })}
          </TableRow>
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function PerClass({ ev }: { ev: SplitEvaluation }) {
  return (
    <TableContainer>
      <Table size="small" aria-label="Métricas por clase">
        <TableHead><TableRow>
          <TableCell>Clase</TableCell><TableCell align="right">n</TableCell><TableCell align="right">Sensibilidad</TableCell>
          <TableCell align="right">Especificidad</TableCell><TableCell align="right">Precisión</TableCell>
          <TableCell align="right">F1</TableCell><TableCell align="right">AUC-ROC</TableCell><TableCell align="right">AUC-PR</TableCell>
        </TableRow></TableHead>
        <TableBody>
          {Object.entries(ev.per_class).map(([c, m]) => (
            <TableRow key={c}>
              <TableCell>{CLASS_LABEL[c] ?? c}</TableCell><TableCell align="right">{m.support}</TableCell>
              <TableCell align="right">{fmtMetric(m.sensitivity)}</TableCell><TableCell align="right">{fmtMetric(m.specificity)}</TableCell>
              <TableCell align="right">{fmtMetric(m.precision)}</TableCell><TableCell align="right">{fmtMetric(m.f1)}</TableCell>
              <TableCell align="right">{fmtMetric(m.auc_roc)}</TableCell><TableCell align="right">{fmtMetric(m.auc_pr)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export function ConfusionMatrix({ ev }: { ev: SplitEvaluation }) {
  const max = Math.max(1, ...ev.confusion_matrix.flat());
  return (
    <TableContainer>
      <Table size="small" aria-label="Matriz de confusión (filas: clase real; columnas: predicha)">
        <TableHead><TableRow>
          <TableCell>Real \ Predicha</TableCell>
          {ev.classes.map((c) => <TableCell key={c} align="center">{CLASS_LABEL[c] ?? c}</TableCell>)}
        </TableRow></TableHead>
        <TableBody>
          {ev.confusion_matrix.map((row, i) => (
            <TableRow key={ev.classes[i]}>
              <TableCell component="th" scope="row">{CLASS_LABEL[ev.classes[i]] ?? ev.classes[i]}</TableCell>
              {row.map((v, j) => (
                <TableCell key={j} align="center"
                  sx={{ bgcolor: i === j ? `rgba(46,107,48,${0.12 + 0.6 * v / max})` : v ? `rgba(179,38,30,${0.08 + 0.5 * v / max})` : undefined,
                    fontWeight: i === j ? 700 : 400 }}>
                  {v}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function Curves({ ev, kind }: { ev: SplitEvaluation; kind: "roc" | "pr" }) {
  const curves = kind === "roc" ? ev.roc_curves : ev.pr_curves;
  if (!curves || !Object.keys(curves).length) return <Typography color="text.secondary">Sin curvas para esta partición.</Typography>;
  return (
    <Box sx={{ height: 260 }} role="img" aria-label={`Curvas ${kind === "roc" ? "ROC" : "precisión-exhaustividad"} por clase`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart margin={{ top: 8, right: 12, left: -12, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" dataKey="x" domain={[0, 1]} tick={{ fontSize: 11 }}
            label={{ value: kind === "roc" ? "1 − especificidad" : "Exhaustividad", position: "insideBottom", offset: -2, fontSize: 11 }} />
          <YAxis type="number" domain={[0, 1]} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => v.toFixed(3)} />
          <Legend />
          {Object.entries(curves).map(([c, cv]) => {
            const xs = kind === "roc" ? (cv as { fpr: number[] }).fpr : (cv as { recall: number[] }).recall;
            const ys = kind === "roc" ? (cv as { tpr: number[] }).tpr : (cv as { precision: number[] }).precision;
            return <Line key={c} data={xs.map((x, i) => ({ x, y: ys[i] }))} dataKey="y" name={CLASS_LABEL[c] ?? c}
              stroke={CLASS_HEX[c] ?? "#555"} dot={false} isAnimationActive={false} />;
          })}
        </LineChart>
      </ResponsiveContainer>
    </Box>
  );
}

function Reliability({ ev }: { ev: SplitEvaluation }) {
  const bins = ev.calibration?.after.bins.filter((b) => b.count > 0) ?? [];
  if (!bins.length) return <Typography color="text.secondary">Sin datos de calibración.</Typography>;
  const data = bins.map((b) => ({ centro: (b.lower + b.upper) / 2, exactitud: b.accuracy, confianza: b.confidence, n: b.count }));
  return (
    <Box sx={{ height: 260 }} role="img" aria-label={`Diagrama de fiabilidad; ECE ${fmtMetric(ev.calibration?.after.ece)}`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" dataKey="centro" domain={[0, 1]} tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => (typeof v === "number" ? v.toFixed(3) : v)} />
          <Legend />
          <Bar dataKey="exactitud" name="Exactitud observada" fill="#2e5e1f" barSize={14} />
          <Line dataKey="confianza" name="Confianza media" stroke="#b07000" dot isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </Box>
  );
}

function TrainingCurves({ hist }: { hist: LabModelDetail["historial"] }) {
  const steps = new Map<number, Record<string, number>>();
  Object.entries(hist).forEach(([k, pts]) => pts.forEach((p) => steps.set(p.step, { ...(steps.get(p.step) ?? { epoca: p.step }), [k]: p.value })));
  const data = [...steps.values()].sort((a, b) => a.epoca - b.epoca);
  if (!data.length) return <Typography color="text.secondary">Sin historial de entrenamiento.</Typography>;
  return (
    <Box sx={{ height: 240 }} role="img" aria-label="Pérdida y macro-F1 de validación por época">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="epoca" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line dataKey="train_loss" name="Pérdida (entrenamiento)" stroke="#45523f" dot={false} isAnimationActive={false} />
          <Line dataKey="val_loss" name="Pérdida (validación)" stroke="#b3261e" dot={false} isAnimationActive={false} />
          <Line dataKey="val_macro_f1_epoch" name="Macro-F1 (validación)" stroke="#2e5e1f" dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </Box>
  );
}

export default function ModelDetailDialog({ modelId, onClose }: { modelId: number | null; onClose(): void }) {
  const q = useQuery({
    queryKey: ["laboratorio", "modelo", modelId],
    queryFn: () => api<LabModelDetail>(`/laboratorio/modelos/${modelId}`),
    enabled: modelId !== null,
  });
  const [split, setSplit] = useState<string>("");
  const d = q.data;
  const splits = d?.evaluacion ? Object.keys(d.evaluacion) : [];
  const current = d?.evaluacion?.[split] ?? (splits.length ? d!.evaluacion![splits[splits.length - 1]] : undefined);
  const cv = d?.validacion_cruzada?.metrics;

  return (
    <Dialog open={modelId !== null} onClose={onClose} fullWidth maxWidth="lg" aria-labelledby="detalle-modelo">
      <DialogTitle id="detalle-modelo">{d?.modelo.display_name ?? "Detalle del modelo"}</DialogTitle>
      <DialogContent dividers>
        {q.isLoading && <CircularProgress aria-label="Cargando" />}
        <ErrorAlert error={q.error} />
        {d && (
          <>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 2 }}>
              <Chip size="small" label={STAGE_LABEL[d.modelo.stage]} />
              <Chip size="small" variant="outlined" label={`Temperatura ${d.modelo.temperature.toFixed(3)}`} />
              {d.modelo.train_dataset_ids.map((ds) => <Chip key={ds} size="small" variant="outlined" label={ds} />)}
              {d.mlflow_url && <Link href={d.mlflow_url} target="_blank" rel="noreferrer">Abrir el run en MLflow</Link>}
            </Box>
            {d.modelo.is_demo && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                {d.modelo.smoke_test ? "Prueba de humo con imágenes sintéticas: las métricas solo demuestran que el pipeline funciona."
                  : "Modelo DEMO sin entrenar."}
              </Alert>
            )}
            {d.mensaje && <Alert severity="info">{d.mensaje}</Alert>}
            {cv && Object.keys(cv).length > 0 && (
              <Typography variant="body2" sx={{ mb: 2 }}>
                Validación cruzada agrupada: macro-F1 {fmtMetric(cv.cv_mean_test_macro_f1)} ± {fmtMetric(cv.cv_std_test_macro_f1)} ·
                MCC {fmtMetric(cv.cv_mean_test_mcc)} ± {fmtMetric(cv.cv_std_test_mcc)}
              </Typography>
            )}
            {d.evaluacion && current && (
              <>
                <Typography variant="h3" component="h3" sx={{ mb: 1 }}>Métricas por partición</Typography>
                <SummaryTable ev={d.evaluacion} />
                <TextField select label="Partición para el detalle" value={current.split} sx={{ mt: 3, mb: 2, maxWidth: 320 }}
                  onChange={(e) => setSplit(e.target.value)}>
                  {splits.map((s) => <MenuItem key={s} value={s}>{SPLIT_LABEL(s)}</MenuItem>)}
                </TextField>
                <Grid container spacing={3}>
                  <Grid size={{ xs: 12, md: 7 }}><Typography variant="subtitle2">Por clase</Typography><PerClass ev={current} /></Grid>
                  <Grid size={{ xs: 12, md: 5 }}><Typography variant="subtitle2">Matriz de confusión</Typography><ConfusionMatrix ev={current} /></Grid>
                  <Grid size={{ xs: 12, md: 4 }}><Typography variant="subtitle2">Curvas ROC</Typography><Curves ev={current} kind="roc" /></Grid>
                  <Grid size={{ xs: 12, md: 4 }}><Typography variant="subtitle2">Curvas precisión-exhaustividad</Typography><Curves ev={current} kind="pr" /></Grid>
                  <Grid size={{ xs: 12, md: 4 }}>
                    <Typography variant="subtitle2">Fiabilidad tras calibrar (ECE {fmtMetric(current.calibration?.after.ece)})</Typography>
                    <Reliability ev={current} />
                  </Grid>
                </Grid>
              </>
            )}
            {d.run && (
              <Grid container spacing={3} sx={{ mt: 1 }}>
                <Grid size={{ xs: 12, md: 7 }}>
                  <Typography variant="subtitle2">Entrenamiento</Typography>
                  <TrainingCurves hist={d.historial} />
                </Grid>
                <Grid size={{ xs: 12, md: 5 }}>
                  <Typography variant="subtitle2">Parámetros</Typography>
                  <Table size="small" aria-label="Parámetros del entrenamiento">
                    <TableBody>
                      {Object.entries(d.run.params).sort().map(([k, v]) => (
                        <TableRow key={k}><TableCell>{k}</TableCell><TableCell>{v}</TableCell></TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Grid>
              </Grid>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Cerrar</Button></DialogActions>
    </Dialog>
  );
}
