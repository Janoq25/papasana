import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, Grid, Link, MenuItem, Paper, Skeleton, Stack, Tab, Tabs, TextField, Typography } from "@mui/material";
import { api } from "../../../api/client";
import ErrorAlert from "../../../components/ErrorAlert";
import { BarFigure, LineFigure, MatrixFigure, MethodologyFigure, type Series } from "./ResearchCharts";
import { Figure, ResearchTable } from "./ResearchWidgets";
import { saveBlob } from "./export";
import { number, shortClass, shortModel, type ReportSummary, type ResearchReport } from "./types";

const splitLabel = (s: string) => s === "val" ? "Validación interna" : s.startsWith("external_") ? "PlantDoc · evaluación descriptiva" : s;
const note = "Piloto con holdout agrupado; no es validación anidada ni prueba prospectiva.";
function ReportView({ report: r }: { report: ResearchReport }) {
  const [view, setView] = useState(0), [widthCm, setWidthCm] = useState(17.5);
  const [architecture, setArchitecture] = useState(r.models[0].architecture), [split, setSplit] = useState("val");
  const model = r.models.find((m) => m.architecture === architecture) ?? r.models[0];
  const currentSplit = model.evaluation[split] ? split : Object.keys(model.evaluation)[0];
  const ev = model.evaluation[currentSplit];
  const categories = r.models.map((m) => shortModel[m.architecture] ?? m.label);
  const caption = `Fuente: ${r.id}. ${note}`;
  const figure = (id: string, title: string, text: string, chart: React.ReactNode) => <Figure key={id} title={title} caption={text} filename={`${r.id}-${id}`} widthCm={widthCm}>{chart}</Figure>;
  const modelFigure = (id: string, title: string, text: string, chart: React.ReactNode) => figure(`${architecture}-${currentSplit}-${id}`, title, text, chart);
  const historySeries = (key: string): Series[] => r.models.map((m) => ({ label: shortModel[m.architecture] ?? m.label, points: (m.history[key] ?? []).map((p) => ({ x: p.step, y: p.value })) }));
  const curveSeries = (kind: "roc" | "pr"): Series[] => Object.entries(kind === "roc" ? ev.roc_curves ?? {} : ev.pr_curves ?? {}).map(([cls, curve]) => {
    const xs = "fpr" in curve ? curve.fpr : curve.recall;
    const ys = "tpr" in curve ? curve.tpr : curve.precision;
    return { label: shortClass[cls] ?? cls, points: xs.map((x: number, i: number) => ({ x, y: ys[i] })) };
  });
  const epochs = [...new Set(Object.values(model.history).flatMap((h) => h.map((p) => p.step)))].sort((a, b) => a - b);
  const metricAt = (key: string, epoch: number) => model.history[key]?.find((p) => p.step === epoch)?.value;
  return <Stack spacing={3}>
    <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 }, borderTop: "4px solid", borderTopColor: "primary.main" }}>
      <Typography variant="overline" color="primary.main" sx={{ letterSpacing: 1.4 }}>Investigación · evidencia reproducible</Typography>
      <Typography variant="h2" component="h2" sx={{ mb: 1 }}>Resultados para el artículo</Typography>
      <Typography color="text.secondary">{r.title}. Datos del {new Date(r.trained_on).toLocaleDateString("es-PE", { timeZone: "America/Lima" })}.</Typography>
      <Stack direction="row" sx={{ my: 2, flexWrap: "wrap", gap: 1 }}>
        <Chip size="small" label={`${r.models.length} modelos entrenados`} /><Chip size="small" variant="outlined" label="Holdout agrupado" />
        <Chip size="small" variant="outlined" label={r.gpu} />
      </Stack>
      <Grid container spacing={2}>
        {[["Entrenamiento", r.data.train], ["Validación interna", r.data.validation], ["PlantDoc externo", r.data.external], ["Hojas agrupadas", r.data.leaf_groups]].map(([label, value]) => <Grid key={label} size={{ xs: 6, md: 3 }}>
          <Typography variant="body2" color="text.secondary">{label}</Typography><Typography sx={{ fontSize: 26, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{number(value as number, 0)}</Typography>
        </Grid>)}
      </Grid>
    </Paper>
    <Alert severity="warning">Resultados piloto. PlantDoc ya fue observado y no contiene hojas sanas: su F1 se calcula sobre las dos clases presentes. El desempeño interno no acredita calidad en campo.</Alert>
    <Box sx={{ display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap" }}>
      <TextField select label="Ancho de imagen al imprimir" value={widthCm} onChange={(e) => setWidthCm(Number(e.target.value))} sx={{ maxWidth: 290 }} helperText="Para figuras con varias series, use 17,5 cm o más.">
        <MenuItem value={8.5}>8,5 cm · una columna</MenuItem><MenuItem value={17.5}>17,5 cm · doble columna</MenuItem><MenuItem value={21}>21 cm · página completa</MenuItem>
      </TextField>
      <Typography variant="body2" color="text.secondary" sx={{ flex: "1 1 220px" }}>Todas las figuras se exportan como PNG a 600 DPI. Las tablas se copian con formato editable para Word o Excel.</Typography>
      <Button variant="outlined" onClick={() => saveBlob(new Blob([JSON.stringify(r, null, 2)], { type: "application/json" }), `${r.id}.json`)}>Descargar datos JSON</Button>
    </Box>
    <Tabs value={view} onChange={(_, v) => setView(v)} variant="scrollable" scrollButtons="auto" allowScrollButtonsMobile aria-label="Contenido de resultados científicos">
      <Tab label="Comparación" id="research-tab-0" aria-controls="research-panel" />
      <Tab label="Detalle por modelo" id="research-tab-1" aria-controls="research-panel" />
      <Tab label="Datos y metodología" id="research-tab-2" aria-controls="research-panel" />
      <Tab label="Trazabilidad" id="research-tab-3" aria-controls="research-panel" />
    </Tabs>
    <Stack spacing={3} id="research-panel" role="tabpanel" aria-labelledby={`research-tab-${view}`}>
    {view === 0 && <>
      <Alert severity="info">Menor tiempo con F1 de referencia: <strong>{r.models.find((m) => m.architecture === r.selection.recommended_architecture)?.label}</strong>. Mayor F1 interno observado: <strong>{r.models.find((m) => m.architecture === r.selection.best_internal_architecture)?.label}</strong>. La selección se fijó antes de la evaluación externa.</Alert>
      <ResearchTable title="Comparación de los modelos entrenados" decimals={{ 1: 4, 2: 4, 3: 4, 4: 4, 5: 2, 6: 1 }} headers={["Modelo", "F1 interno (3 clases)", "Exactitud interna", "F1 PlantDoc (2 clases)", "Exactitud PlantDoc", "Tiempo (s)", "VRAM pico (MB)", "Mejor época"]}
        rows={r.models.map((m) => [m.label, m.metrics.val_macro_f1, m.metrics.val_accuracy, m.evaluation.external_plantdoc_papa?.macro_f1, m.evaluation.external_plantdoc_papa?.accuracy, m.metrics.train_seconds, m.metrics.gpu_peak_memory_mb, m.best_epoch])} note={`${caption} Tiempo del ajuste exitoso; excluye descargas y el intento FP16 fallido.`} />
      {figure("f1-comparacion", "F1 por arquitectura", "Cada barra indica su conjunto y número de clases; las fuentes tienen condiciones distintas.", <BarFigure title="F1 por arquitectura y dominio" subtitle="PlantVillage: laboratorio · PlantDoc: campo, uso descriptivo" categories={categories} series={[{ label: "Validación interna · tres clases", values: r.models.map((m) => m.metrics.val_macro_f1) }, { label: "PlantDoc · dos clases presentes", values: r.models.map((m) => m.evaluation.external_plantdoc_papa?.macro_f1 ?? null) }]} max={1} note="No se ha demostrado no inferioridad estadística. La calidad de campo sigue limitada." />)}
      {figure("tiempo", "Tiempo de entrenamiento", "Tiempos medidos en esta laptop. La parada anticipada produce distinta cantidad de épocas.", <BarFigure title="Tiempo de los ajustes exitosos" subtitle={r.gpu} categories={categories} series={[{ label: "Tiempo registrado por el entrenador", values: r.models.map((m) => m.metrics.train_seconds) }]} unit="Segundos" note="Mismo máximo: 16 épocas; parada tras cuatro sin mejora. Se conserva el mejor checkpoint." />)}
      {figure("memoria", "Memoria de GPU", "Memoria máxima asignada por PyTorch durante cada ajuste; no es la memoria total del sistema.", <BarFigure title="Memoria de GPU durante el ajuste" categories={categories} series={[{ label: "Máximo asignado por PyTorch", values: r.models.map((m) => m.metrics.gpu_peak_memory_mb) }]} unit="MB" note="Lote físico 16; acumulación de dos pasos. FP16 o BF16 según el modelo." />)}
      {figure("curvas-f1", "Evolución del F1 de validación", "Historial real por época. Se conservó el mejor checkpoint de cada arquitectura.", <LineFigure title="F1 interno a lo largo del entrenamiento" series={historySeries("val_macro_f1_epoch")} xLabel="Época" yLabel="F1 macro · tres clases" maxY={1} note={`${r.data.validation} imágenes internas; separación por hoja. ${note}`} />)}
    </>}
    {view === 1 && <>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
        <TextField select label="Modelo del entrenamiento" value={architecture} onChange={(e) => setArchitecture(e.target.value)} sx={{ maxWidth: 350 }}>{r.models.map((m) => <MenuItem value={m.architecture} key={m.architecture}>{m.label}</MenuItem>)}</TextField>
        <TextField select label="Conjunto de evaluación" value={currentSplit} onChange={(e) => setSplit(e.target.value)} sx={{ maxWidth: 350 }}>{Object.keys(model.evaluation).map((s) => <MenuItem value={s} key={s}>{splitLabel(s)}</MenuItem>)}</TextField>
      </Box>
      <ResearchTable title={`Métricas por clase · ${model.label}`} decimals={{ 2: 4, 3: 4, 4: 4, 5: 4, 6: 4, 7: 4 }} headers={["Clase", "Imágenes", "Sensibilidad", "Especificidad", "Precisión", "F1", "AUC-ROC", "AUC-PR"]} rows={Object.entries(ev.per_class).map(([cls, pc]) => [shortClass[cls] ?? cls, pc.support, pc.sensitivity, pc.specificity, pc.precision, pc.support ? pc.f1 : null, pc.auc_roc, pc.auc_pr])} note={`${model.label} · ${splitLabel(currentSplit)} · n=${ev.n}. «—» indica valor no disponible. ${caption}`} />
      {modelFigure("confusion", "Matriz de confusión", `${model.label} · ${splitLabel(currentSplit)}. Los valores son cantidades de imágenes.`, <MatrixFigure title={`Matriz de confusión · ${shortModel[architecture] ?? model.label}`} subtitle={`${splitLabel(currentSplit)} · ${ev.n} imágenes`} matrix={ev.confusion_matrix} labels={ev.classes} note="Filas: referencia por síntomas. Columnas: predicción. Una clase ausente no se valida." />)}
      {(["roc", "pr"] as const).map((kind) => curveSeries(kind).length ? modelFigure(kind, kind === "roc" ? "Curvas ROC" : "Curvas precisión-exhaustividad", `${model.label} · ${splitLabel(currentSplit)}. Solo clases con soporte; esquema uno contra el resto.`, <LineFigure title={`${kind === "roc" ? "ROC" : "Precisión-exhaustividad"} · ${shortModel[architecture] ?? model.label}`} subtitle={`${splitLabel(currentSplit)} · n=${ev.n}`} series={curveSeries(kind)} xLabel={kind === "roc" ? "Tasa de falsos positivos" : "Exhaustividad / sensibilidad"} yLabel={kind === "roc" ? "Sensibilidad" : "Precisión"} maxY={1} diagonal={kind === "roc"} note="Las curvas de clases sin referencia se omiten; no se inventan valores." />) : <Alert key={kind} severity="info">No hay curvas {kind.toUpperCase()} guardadas para este conjunto.</Alert>)}
      {ev.calibration && modelFigure("calibracion", "Fiabilidad antes y después de calibrar", `ECE antes: ${number(ev.calibration.before.ece)}; después: ${number(ev.calibration.after.ece)}. Temperatura ajustada solo en validación interna.`, <LineFigure title={`Calibración · ${shortModel[architecture] ?? model.label}`} subtitle={`${splitLabel(currentSplit)} · temperatura T=${number(ev.calibration.temperature)}`} series={(["before", "after"] as const).map((key) => ({ label: key === "before" ? "Antes de calibrar" : "Después de calibrar", points: ev.calibration![key].bins.filter((b) => b.count > 0 && b.confidence !== null && b.accuracy !== null).map((b) => ({ x: b.confidence!, y: b.accuracy! })) }))} xLabel="Confianza media del intervalo" yLabel="Exactitud observada" maxY={1} diagonal note="Diagonal: calibración ideal. Se muestran solo intervalos con imágenes." />)}
      {figure(`${architecture}-perdida`, "Pérdida durante el entrenamiento", "Entrenamiento usa ponderación por clase; la pérdida de validación no está ponderada.", <LineFigure title={`Pérdida · ${shortModel[architecture] ?? model.label}`} series={[{ label: "Entrenamiento (ponderado)", points: (model.history.train_loss ?? []).map((p) => ({ x: p.step, y: p.value })) }, { label: "Validación", points: (model.history.val_loss ?? []).map((p) => ({ x: p.step, y: p.value })) }]} xLabel="Época" yLabel="Entropía cruzada" note="Se comparan tendencias; el checkpoint se elige por F1 interno y pérdida de desempate." />)}
      <ResearchTable title={`Historial por época · ${model.label}`} decimals={{ 1: 6, 2: 6, 3: 4 }} headers={["Época", "Pérdida entrenamiento", "Pérdida validación", "F1 validación", "Tasa de aprendizaje"]} rows={epochs.map((epoch) => [epoch, metricAt("train_loss", epoch), metricAt("val_loss", epoch), metricAt("val_macro_f1_epoch", epoch), metricAt("lr", epoch)?.toExponential(6)])} note={`Run ${model.run_id}. Mejor época: ${model.best_epoch}. ${caption}`} />
    </>}
    {view === 2 && <>
      {figure("metodologia", "Metodología de la investigación", "Flujo realmente ejecutado, desde las fuentes y el EDA hasta los resultados. La rama externa se mantiene fuera del ajuste y la selección. La validación anidada sigue pendiente.", <MethodologyFigure report={r} />)}
      <ResearchTable title="Control de calidad y particiones" headers={["Etapa", "Imágenes / grupos", "Criterio"]} rows={[["Imágenes originales", r.data.original, "Fuentes públicas verificadas"], ["Copias exactas retiradas", r.data.duplicates_removed, "SHA-256"], ["Imágenes en cuarentena", r.data.quarantined, "Grupos perceptuales con etiquetas conflictivas"], ["Imágenes utilizables", r.data.accepted, "Tras retirar copias y cuarentena"], ["Entrenamiento", r.data.train, "PlantVillage; hojas fuera del fold de validación"], ["Validación interna", r.data.validation, `PlantVillage; fold ${r.data.validation_fold}`], ["Evaluación externa", r.data.external, "PlantDoc; dos clases, sin sanos"], ["Hojas de desarrollo", r.data.leaf_groups, "Agrupación por identificador físico de hoja"]]} note={caption} />
      <ResearchTable title="Distribución de clases por fuente" headers={["Fuente", "Uso", ...r.classes.map((c) => shortClass[c] ?? c), "Total"]} rows={r.data.datasets.map((ds) => [ds.id, ds.role, ...r.classes.map((c) => ds.counts[c]), ds.n])} note={`Recuentos posteriores al control de calidad. ${caption}`} />
      {r.data.datasets.map((ds) => figure(`clases-${ds.id}`, `Distribución de clases · ${ds.id}`, "Recuentos reales tras el control de calidad. El desbalance se consideró mediante ponderación de la pérdida.", <BarFigure title={`Clases · ${ds.id}`} subtitle={`${ds.n} imágenes utilizables · ${ds.role}`} categories={r.classes.map((c) => c === "sintomas_compatibles_tizon_tardio" ? "Síntomas compatibles\ncon tizón tardío" : c === "otra_enfermedad_foliar" ? "Otra enfermedad\nfoliar" : "Sano")} series={[{ label: "Imágenes", values: r.classes.map((c) => ds.counts[c]) }]} unit="Imágenes" note={ds.role === "externo" ? "Sin hojas sanas de papa: no permite validar la clase sano." : "Las hojas físicas no se comparten entre folds."} />))}
      {figure("folds", "Particiones de desarrollo", "Se prepararon cinco folds; esta comparación utilizó uno para validación y los cuatro restantes para entrenamiento.", <BarFigure title="Distribución de imágenes por fold" categories={r.data.folds.map((f) => `Fold ${f.fold}${f.fold === r.data.validation_fold ? "\nValidación" : "\nEntrenamiento"}`)} series={[{ label: "PlantVillage · desarrollo", values: r.data.folds.map((f) => f.n) }]} unit="Imágenes" note="Esta ejecución es un holdout agrupado, no una validación cruzada completa." />)}
      <ResearchTable title="Recuento por fold" headers={["Fold", ...r.classes.map((c) => shortClass[c] ?? c), "Imágenes", "Uso en esta ejecución"]} rows={r.data.folds.map((f) => [f.fold, ...r.classes.map((c) => f.counts[c]), f.n, f.fold === r.data.validation_fold ? "Validación" : "Entrenamiento"])} note={caption} />
      <ResearchTable title="Resolución original de las imágenes" headers={["Estadístico", "Ancho (px)", "Alto (px)"]} rows={r.data.resolution.map((row) => [row.metric, row.width, row.height])} note={`Dimensiones anteriores al redimensionado a 224 × 224 px. ${caption}`} />
    </>}
    {view === 3 && <>
      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Typography variant="h3" component="h3">Procedencia del informe</Typography>
        <Typography variant="body2" sx={{ mt: 1, overflowWrap: "anywhere" }}>Manifest SHA-256: {r.manifest_sha256}</Typography>
        <Typography variant="body2" sx={{ mt: 1, overflowWrap: "anywhere" }}>Contrato del experimento: {r.fingerprint}</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>PyTorch {r.torch}. Informe generado: {new Date(r.generated_at).toLocaleString("es-PE")}.</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>Se conserva un informe publicado del experimento; consultar esta sección no reentrena ni cambia el modelo activo.</Typography>
      </Paper>
      <ResearchTable title="Configuración de los entrenamientos" headers={["Parámetro", ...r.models.map((m) => m.label)]} rows={[["Resolución (px)", ...r.models.map((m) => m.img_size)], ["Parámetros del modelo", ...r.models.map((m) => m.parameters)], ["Peso del checkpoint (MB)", ...r.models.map((m) => m.checkpoint_mb)], ...Object.keys(r.models[0].train).map((key) => [key, ...r.models.map((m) => typeof m.train[key] === "boolean" ? (m.train[key] ? "sí" : "no") : m.train[key])])]} note={`Optimizador AdamW. El intento FP16 fallido de MobileNetV4 está excluido. ${caption}`} />
      <ResearchTable title="Identificadores y verificación de checkpoints" headers={["Modelo", "Run de MLflow", "SHA-256 del checkpoint"]} rows={r.models.map((m) => [m.label, m.run_id, m.checkpoint_sha256])} note="Los cuatro checkpoints se recargaron en CUDA; Grad-CAM 7×7 y la reproducción de predicciones guardadas fueron verificados." />
      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Typography variant="h3" component="h3" sx={{ mb: 1 }}>Fuentes y licencias</Typography>
        <Stack spacing={1}>{r.data_sources.map((source) => <Typography key={source.title} variant="body2"><Link href={source.url} target="_blank" rel="noreferrer">{source.title}</Link> · {source.license}</Typography>)}
          {r.model_sources.map((source) => <Typography key={source.architecture} variant="body2" sx={{ overflowWrap: "anywhere" }}><Link href={source.license_source} target="_blank" rel="noreferrer">{source.repo}</Link> · {source.license} · revisión {source.revision}</Typography>)}</Stack>
      </Paper>
      <ResearchTable title="Limitaciones para la interpretación científica" headers={["N.º", "Limitación"]} rows={r.limitations.map((limit, i) => [i + 1, limit])} note="Estas limitaciones acompañan las tablas para evitar presentar el piloto como una validación agronómica definitiva." />
    </>}
    </Stack>
  </Stack>;
}
export default function ResearchTab() {
  const [selected, setSelected] = useState("");
  const index = useQuery({ queryKey: ["laboratorio", "publicaciones"], queryFn: () => api<ReportSummary[]>("/laboratorio/publicaciones") });
  const id = selected || index.data?.[0]?.id || "";
  const report = useQuery({ queryKey: ["laboratorio", "publicacion", id], queryFn: () => api<ResearchReport>(`/laboratorio/publicaciones/${encodeURIComponent(id)}`), enabled: !!id });
  if (index.isLoading || (!!id && report.isLoading)) return <Box role="status" aria-label="Cargando resultados científicos"><Skeleton height={170} /><Skeleton height={340} /></Box>;
  if (index.error || report.error) return <Box><ErrorAlert error={index.error ?? report.error} /><Button onClick={() => { void index.refetch(); void report.refetch(); }}>Reintentar cargar resultados</Button></Box>;
  if (!index.data?.length) return <Alert severity="info">Todavía no hay informes de entrenamiento publicados para el artículo. Publique un experimento terminado para visualizar sus resultados.</Alert>;
  return <Stack spacing={3}>
    <TextField select label="Informe de entrenamiento" value={id} onChange={(e) => setSelected(e.target.value)} sx={{ maxWidth: 600 }}>{index.data.map((item) => <MenuItem key={item.id} value={item.id}>{item.title} · {new Date(item.trained_on).toLocaleDateString("es-PE", { timeZone: "America/Lima" })}</MenuItem>)}</TextField>
    {report.data && <ReportView key={report.data.id} report={report.data} />}
  </Stack>;
}
