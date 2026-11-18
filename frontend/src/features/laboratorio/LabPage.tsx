import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Badge,
  Box,
  Button,
  Chip,
  Link,
  Paper,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Typography,
} from "@mui/material";
import SyncIcon from "@mui/icons-material/Sync";
import { api } from "../../api/client";
import type { LabModel, LabStatus, Promotion } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import ComparisonTab from "./ComparisonTab";
import { ARCH_LABEL, canPromote, canRollbackTo, fmtMetric, STAGE_COLOR, STAGE_LABEL, summarize } from "./labUtils";
import ModelDetailDialog from "./ModelDetailDialog";
import PromotionsTab, { RequestDialog } from "./PromotionsTab";

function ServiceStatus({ status }: { status?: LabStatus }) {
  if (!status) return null;
  const ml = status.ml_service && "key" in status.ml_service ? status.ml_service : null;
  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2, display: "flex", flexWrap: "wrap", gap: 2, alignItems: "center" }}>
      <Box sx={{ flexGrow: 1 }}>
        <Typography variant="body2" color="text.secondary">Modelo en uso por ml-service</Typography>
        <Typography sx={{ fontWeight: 600 }}>{ml ? ml.display_name : "No disponible"}</Typography>
        {ml?.load_status?.detalle && (
          <Typography variant="caption" color="text.secondary">{ml.load_status.detalle}</Typography>
        )}
      </Box>
      {ml?.is_demo && <Chip color="warning" label="DEMO / no validado" />}
      <Chip variant="outlined" color={status.mlflow_disponible ? "success" : "error"}
        label={status.mlflow_disponible ? "MLflow disponible" : "MLflow no responde"} />
      <Link href={status.mlflow_url} target="_blank" rel="noreferrer">Abrir MLflow</Link>
    </Paper>
  );
}

function ModelsTable({ models, promotions, onDetail, onRequest }: {
  models: LabModel[];
  promotions: Promotion[];
  onDetail(id: number): void;
  onRequest(m: LabModel, action: "promover" | "rollback"): void;
}) {
  const { can } = useAuth();
  const productionInUse = models.some((m) => m.stage === "production");
  const pending = promotions.some((p) => p.status === "pendiente");
  const canRequest = can("laboratorio:crear") && !pending;
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small" aria-label="Versiones de modelo">
        <TableHead><TableRow>
          <TableCell>Versión</TableCell><TableCell>Arquitectura</TableCell><TableCell>Etapa</TableCell>
          <TableCell align="right">Macro-F1 validación</TableCell><TableCell align="right">Macro-F1 CV (media ± DE)</TableCell>
          <TableCell align="right">Macro-F1 externa</TableCell><TableCell align="right">ECE</TableCell>
          <TableCell>Datasets</TableCell><TableCell align="right">Acciones</TableCell>
        </TableRow></TableHead>
        <TableBody>
          {models.map((m) => {
            const s = summarize(m);
            return (
              <TableRow key={m.id} hover selected={m.stage === "production"}>
                <TableCell>
                  {m.display_name}
                  {m.smoke_test && <Chip size="small" color="warning" label="Prueba de humo" sx={{ ml: 1 }} />}
                  {m.source === "demo" && <Chip size="small" color="warning" label="Sin entrenar" sx={{ ml: 1 }} />}
                </TableCell>
                <TableCell>{ARCH_LABEL[m.architecture] ?? m.architecture}</TableCell>
                <TableCell><Chip size="small" color={STAGE_COLOR[m.stage]} label={STAGE_LABEL[m.stage]} /></TableCell>
                <TableCell align="right">{fmtMetric(s.valF1)}</TableCell>
                <TableCell align="right">{s.cvF1 === null ? "—" : `${fmtMetric(s.cvF1)} ± ${fmtMetric(s.cvF1Std)}`}</TableCell>
                <TableCell align="right" title={s.extName ?? undefined}>{fmtMetric(s.extF1)}</TableCell>
                <TableCell align="right">{fmtMetric(s.ece)}</TableCell>
                <TableCell>{m.train_dataset_ids.join(", ") || "—"}</TableCell>
                <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                  <Button size="small" onClick={() => onDetail(m.id)}>Detalle</Button>
                  {canRequest && canPromote(m) && (
                    <Button size="small" onClick={() => onRequest(m, "promover")}>Promover</Button>
                  )}
                  {canRequest && canRollbackTo(m, promotions, productionInUse) && (
                    <Button size="small" color="warning" onClick={() => onRequest(m, "rollback")}>Rollback</Button>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default function LabPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);
  const [detail, setDetail] = useState<number | null>(null);
  const [request, setRequest] = useState<{ m: LabModel; action: "promover" | "rollback" } | null>(null);
  const models = useQuery({ queryKey: ["laboratorio", "modelos"], queryFn: () => api<LabModel[]>("/laboratorio/modelos") });
  const promotions = useQuery({ queryKey: ["laboratorio", "promociones"], queryFn: () => api<Promotion[]>("/laboratorio/promociones") });
  const status = useQuery({ queryKey: ["laboratorio", "estado"], queryFn: () => api<LabStatus>("/laboratorio/estado") });
  const sync = useMutation({
    mutationFn: () => api<{ creados: number; actualizados: number }>("/laboratorio/sincronizar", { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["laboratorio"] }),
  });
  const list = models.data ?? [];
  const onlyDemo = models.isSuccess && list.every((m) => m.source === "demo");
  const pendingCount = (promotions.data ?? []).filter((p) => p.status === "pendiente").length;

  return (
    <Box>
      <PageHeader title="Laboratorio de modelos"
        subtitle="Versiones registradas en MLflow, métricas, comparación estadística y promoción con cuatro ojos."
        actions={(can("laboratorio:crear") || can("laboratorio:aprobar")) && (
          <Button variant="outlined" startIcon={<SyncIcon />} disabled={sync.isPending} onClick={() => sync.mutate()}>
            Sincronizar con MLflow
          </Button>
        )} />
      <ErrorAlert error={models.error ?? sync.error ?? status.error} />
      {sync.data && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => sync.reset()}>
          Registro sincronizado: {sync.data.creados} versiones nuevas y {sync.data.actualizados} actualizadas.
        </Alert>
      )}
      <ServiceStatus status={status.data} />
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }} aria-label="Vistas del laboratorio">
        <Tab label="Modelos" />
        <Tab label="Comparación estadística" />
        <Tab label={<Badge color="warning" badgeContent={pendingCount}>Promociones&nbsp;&nbsp;</Badge>} />
      </Tabs>
      {tab === 0 && (
        <>
          {onlyDemo && (
            <Alert severity="info" sx={{ mb: 2 }}>
              <strong>Sin experimentos registrados.</strong> Solo existe el modelo DEMO (sin entrenar, sin métricas).
              Entrene y registre modelos con el paquete <code>ml/</code> (ver docs/guia_entrenamiento.md) y luego
              sincronice.
            </Alert>
          )}
          <ModelsTable models={list} promotions={promotions.data ?? []} onDetail={setDetail}
            onRequest={(m, action) => setRequest({ m, action })} />
        </>
      )}
      {tab === 1 && <ComparisonTab />}
      {tab === 2 && <PromotionsTab promotions={promotions.data ?? []} />}
      <ModelDetailDialog modelId={detail} onClose={() => setDetail(null)} />
      <RequestDialog target={request?.m ?? null} action={request?.action ?? "promover"} onClose={() => setRequest(null)} />
    </Box>
  );
}
