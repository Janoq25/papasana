import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../../api/client";
import type { LabModel, Promotion } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import ErrorAlert from "../../components/ErrorAlert";
import { formatDateTime } from "../../utils/format";
import { PROMOTION_STATUS_COLOR, PROMOTION_STATUS_LABEL } from "./labUtils";

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ["laboratorio"] });
  void qc.invalidateQueries({ queryKey: ["notificaciones"] });
}

export function RequestDialog({ target, action, onClose }: {
  target: LabModel | null;
  action: "promover" | "rollback";
  onClose(): void;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const m = useMutation({
    mutationFn: () => api<Promotion>("/laboratorio/promociones", {
      method: "POST", body: { model_version_id: target!.id, action, reason },
    }),
    onSuccess: () => { invalidate(qc); setReason(""); onClose(); },
  });
  return (
    <Dialog open={!!target} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{action === "promover" ? "Solicitar la promoción a producción" : "Solicitar un rollback"}</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>
          {target?.display_name}. La solicitud debe aprobarla <strong>otra persona</strong> con permiso de aprobación
          (principio de cuatro ojos). Al aprobarse, ml-service carga este modelo y todo queda en la bitácora.
        </DialogContentText>
        {target?.smoke_test && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Es un modelo de prueba de humo: se servirá marcado como DEMO / no validado y sus métricas no se reportan.
          </Alert>
        )}
        <ErrorAlert error={m.error} />
        <TextField label="Motivo (obligatorio)" multiline minRows={3} value={reason} autoFocus
          onChange={(e) => setReason(e.target.value)} helperText="Por ejemplo: resultados de validación externa, comparación estadística, problema detectado en campo." />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="contained" disabled={reason.trim().length < 10 || m.isPending} onClick={() => m.mutate()}>
          Enviar solicitud
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function DecisionDialog({ promotion, mode, onClose }: {
  promotion: Promotion | null;
  mode: "aprobar" | "rechazar" | "cancelar";
  onClose(): void;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const path = mode === "aprobar" ? "aprobar" : "rechazar";
  const m = useMutation({
    mutationFn: () => api<Promotion>(`/laboratorio/promociones/${promotion!.id}/${path}`, { method: "POST", body: { reason } }),
    onSuccess: () => { invalidate(qc); setReason(""); onClose(); },
    onError: () => invalidate(qc),
  });
  const title = mode === "aprobar" ? "Aprobar y aplicar" : mode === "rechazar" ? "Rechazar la solicitud" : "Cancelar mi solicitud";
  return (
    <Dialog open={!!promotion} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>
          {promotion?.action === "rollback" ? "Rollback a" : "Promover"}: <strong>{promotion?.model_version.display_name}</strong>.
          {mode === "aprobar" && " Se moverá el alias production en MLflow y ml-service recargará el modelo; si falla, se restaura el anterior."}
        </DialogContentText>
        <ErrorAlert error={m.error} />
        <TextField label={mode === "aprobar" ? "Comentario (opcional)" : "Motivo (obligatorio)"} multiline minRows={2}
          value={reason} onChange={(e) => setReason(e.target.value)} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Volver</Button>
        <Button variant="contained" color={mode === "aprobar" ? "primary" : "error"}
          disabled={m.isPending || (mode !== "aprobar" && !reason.trim())} onClick={() => m.mutate()}>
          {title}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function PromotionsTab({ promotions }: { promotions: Promotion[] }) {
  const { user, can } = useAuth();
  const [decision, setDecision] = useState<{ p: Promotion; mode: "aprobar" | "rechazar" | "cancelar" } | null>(null);
  const pending = promotions.filter((p) => p.status === "pendiente");

  return (
    <Box>
      {pending.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2, borderColor: "warning.main" }}>
          <Typography variant="h3" component="h3" sx={{ mb: 1 }}>Pendientes de aprobación</Typography>
          {pending.map((p) => {
            const own = p.requested_by === user?.id;
            return (
              <Box key={p.id} sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1, py: 1 }}>
                <Box sx={{ flexGrow: 1 }}>
                  <Typography><strong>{p.action === "rollback" ? "Rollback a" : "Promover"}:</strong> {p.model_version.display_name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {p.requested_by_name} · {formatDateTime(p.created_at)} · {p.request_reason}
                  </Typography>
                </Box>
                {own ? (
                  <>
                    <Chip size="small" label="Su solicitud: la aprueba otra persona" />
                    <Button size="small" onClick={() => setDecision({ p, mode: "cancelar" })}>Cancelar</Button>
                  </>
                ) : can("laboratorio:aprobar") ? (
                  <>
                    <Button size="small" variant="contained" onClick={() => setDecision({ p, mode: "aprobar" })}>Aprobar</Button>
                    <Button size="small" color="error" onClick={() => setDecision({ p, mode: "rechazar" })}>Rechazar</Button>
                  </>
                ) : null}
              </Box>
            );
          })}
        </Paper>
      )}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label="Historial de promociones">
          <TableHead><TableRow>
            <TableCell>Fecha</TableCell><TableCell>Acción</TableCell><TableCell>Modelo</TableCell>
            <TableCell>Anterior</TableCell><TableCell>Solicitó</TableCell><TableCell>Decidió</TableCell><TableCell>Estado</TableCell>
          </TableRow></TableHead>
          <TableBody>
            {promotions.length === 0 && <TableRow><TableCell colSpan={7}>Sin promociones registradas.</TableCell></TableRow>}
            {promotions.map((p) => (
              <TableRow key={p.id}>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDateTime(p.created_at)}</TableCell>
                <TableCell>{p.action === "rollback" ? "Rollback" : "Promoción"}</TableCell>
                <TableCell>{p.model_version.display_name}</TableCell>
                <TableCell>{p.previous?.display_name ?? "DEMO"}</TableCell>
                <TableCell>{p.requested_by_name}</TableCell>
                <TableCell>{p.decided_by_name ?? "—"}</TableCell>
                <TableCell>
                  <Chip size="small" color={PROMOTION_STATUS_COLOR[p.status]} label={PROMOTION_STATUS_LABEL[p.status]}
                    title={p.error ?? p.decision_reason ?? undefined} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <DecisionDialog promotion={decision?.p ?? null} mode={decision?.mode ?? "aprobar"} onClose={() => setDecision(null)} />
    </Box>
  );
}
