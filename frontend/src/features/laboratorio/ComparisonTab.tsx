import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { api } from "../../api/client";
import type { Comparison } from "../../api/types";
import ErrorAlert from "../../components/ErrorAlert";
import { ARCH_LABEL, fmtMetric, fmtP } from "./labUtils";

const name = (m: string) => ARCH_LABEL[m] ?? m;
const sig = (p: number | undefined) => (p !== undefined && p < 0.05 ? <Chip size="small" color="primary" label="p < 0,05" /> : null);

function Section({ title, children, note }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Typography variant="h3" component="h3">{title}</Typography>
      {note && <Typography variant="caption" color="text.secondary" component="p">{note}</Typography>}
      <Box sx={{ mt: 1 }}>{children}</Box>
    </Paper>
  );
}

export default function ComparisonTab() {
  const q = useQuery({ queryKey: ["laboratorio", "comparacion"], queryFn: () => api<Comparison>("/laboratorio/comparacion") });
  if (q.isLoading) return <CircularProgress aria-label="Cargando" />;
  if (q.error) return <ErrorAlert error={q.error} />;
  const c = q.data!;
  if (c.estado !== "ok") {
    return <Alert severity="info">{c.mensaje ?? "Sin experimentos registrados."}</Alert>;
  }
  const models = c.modelos ?? [];
  return (
    <Box>
      {c.solo_prueba_de_humo && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Esta comparación se calculó con runs de <strong>prueba de humo</strong> (imágenes sintéticas): demuestra
          que el cálculo funciona, pero sus valores no tienen valor científico.
        </Alert>
      )}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Métrica: {c.metrica} · {c.bloques?.length ?? 0} bloques (partición × escenario) · {c.oof_imagenes ?? 0} imágenes
        fuera de partición comparadas en McNemar, DeLong y bootstrap.
      </Typography>

      <Section title="Desempeño por modelo" note="Media y desviación estándar sobre los bloques; rango medio de Friedman (1 = mejor).">
        <TableContainer>
          <Table size="small" aria-label="Desempeño por modelo">
            <TableHead><TableRow>
              <TableCell>Modelo</TableCell><TableCell align="right">Media</TableCell><TableCell align="right">Desv.</TableCell>
              <TableCell align="right">Rango medio</TableCell><TableCell align="right">Macro-F1 (IC 95 %)</TableCell>
              <TableCell align="right">MCC (IC 95 %)</TableCell>
            </TableRow></TableHead>
            <TableBody>
              {models.map((m) => {
                const pm = c.por_modelo?.[m];
                const b = c.bootstrap?.[m];
                const ci = (k: string) => b?.[k] ? `${fmtMetric(b[k].valor)} (${fmtMetric(b[k].ic_inferior)}–${fmtMetric(b[k].ic_superior)})` : "—";
                return (
                  <TableRow key={m}>
                    <TableCell>{name(m)}</TableCell>
                    <TableCell align="right">{fmtMetric(pm?.media)}</TableCell>
                    <TableCell align="right">{fmtMetric(pm?.desviacion)}</TableCell>
                    <TableCell align="right">{fmtMetric(c.friedman?.rango_medio?.[m], 2)}</TableCell>
                    <TableCell align="right">{ci("macro_f1")}</TableCell>
                    <TableCell align="right">{ci("mcc")}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Section>

      <Section title="Prueba de Friedman" note="Sobre las métricas por bloque, nunca sobre valores agregados de una sola partición.">
        {c.friedman?.aplicable ? (
          <Typography>χ² = {fmtMetric(c.friedman.estadistico)} · p = {fmtP(c.friedman.p_valor)} · {c.friedman.bloques} bloques {sig(c.friedman.p_valor)}</Typography>
        ) : <Typography color="text.secondary">No aplicable: {c.friedman?.motivo}</Typography>}
      </Section>

      <PairTable title="Wilcoxon por pares (corrección de Holm)" rows={c.wilcoxon_holm ?? []}
        cols={[["Diferencia media", (r) => fmtMetric(r.diferencia_media as number)], ["p", (r) => fmtP(r.p_valor)],
          ["p (Holm)", (r) => <>{fmtP(r.p_holm as number)} {sig(r.p_holm as number)}</>]]} />
      <PairTable title="McNemar (mismas imágenes)" rows={c.mcnemar ?? []}
        cols={[["Acierta solo A", (r) => String(r.n01)], ["Acierta solo B", (r) => String(r.n10)],
          ["Método", (r) => String(r.metodo)], ["p", (r) => <>{fmtP(r.p_valor)} {sig(r.p_valor)}</>]]} />
      <PairTable title="DeLong (AUC de síntomas compatibles con tizón tardío)" rows={c.delong ?? []}
        cols={[["AUC A", (r) => fmtMetric(r.auc_a as number)], ["AUC B", (r) => fmtMetric(r.auc_b as number)],
          ["p", (r) => (r.aplicable ? <>{fmtP(r.p_valor)} {sig(r.p_valor)}</> : "No aplicable")]]} />
    </Box>
  );
}

function PairTable<T extends { modelo_a: string; modelo_b: string; p_valor: number }>({ title, rows, cols }: {
  title: string;
  rows: T[];
  cols: [string, (r: T) => React.ReactNode][];
}) {
  return (
    <Section title={title}>
      {rows.length === 0 ? <Typography color="text.secondary">Se necesitan al menos dos modelos.</Typography> : (
        <TableContainer>
          <Table size="small" aria-label={title}>
            <TableHead><TableRow>
              <TableCell>Modelo A</TableCell><TableCell>Modelo B</TableCell>
              {cols.map(([h]) => <TableCell key={h} align="right">{h}</TableCell>)}
            </TableRow></TableHead>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={`${r.modelo_a}-${r.modelo_b}`}>
                  <TableCell>{name(r.modelo_a)}</TableCell><TableCell>{name(r.modelo_b)}</TableCell>
                  {cols.map(([h, f]) => <TableCell key={h} align="right">{f(r)}</TableCell>)}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Section>
  );
}
