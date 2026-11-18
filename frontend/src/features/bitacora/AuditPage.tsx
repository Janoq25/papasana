import { Fragment, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import ExportReportDialog from "../reportes/ExportReportDialog";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  Grid,
  IconButton,
  MenuItem,
  Paper,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import VerifiedIcon from "@mui/icons-material/Verified";
import { api } from "../../api/client";
import type { AuditEntry, ModuleTime, Page, VerifyResult } from "../../api/types";
import { MENU, moduleLabel } from "../../app/modules";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import { EVENT_LABELS, formatDateTime, formatDuration, limaDayStartIso, limaNextDayStartIso } from "../../utils/format";

const MODULE_OPTIONS = [...new Set(["auth", "perfil", ...MENU.map((m) => m.module)])];

interface Filters {
  user_email: string;
  module_code: string;
  event_type: string;
  result: string;
  from: string;
  to: string;
}

const EMPTY: Filters = { user_email: "", module_code: "", event_type: "", result: "", from: "", to: "" };

function toQuery(f: Filters) {
  return {
    user_email: f.user_email.trim(),
    module_code: f.module_code,
    event_type: f.event_type,
    result: f.result,
    date_from: f.from ? limaDayStartIso(f.from) : undefined,
    date_to: f.to ? limaNextDayStartIso(f.to) : undefined,
  };
}

export default function AuditPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState(0);
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [exportOpen, setExportOpen] = useState(false);

  return (
    <Box>
      <PageHeader
        title="Bitácora de auditoría"
        subtitle="Registro inmutable (append-only) con hash encadenado. Horas en zona America/Lima."
        actions={
          can("bitacora:exportar") && (
            <Button variant="outlined" onClick={() => setExportOpen(true)}>Exportar</Button>
          )
        }
      />
      <FiltersBar filters={filters} onChange={setFilters} />
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }} aria-label="Vistas de la bitácora">
        <Tab label="Registros" />
        <Tab label="Línea de tiempo" />
        <Tab label="Permanencia por módulo" />
        <Tab label="Integridad" />
      </Tabs>
      {tab === 0 && <RecordsTab filters={filters} />}
      {tab === 1 && <TimelineTab filters={filters} />}
      {tab === 2 && <ModuleTimeTab filters={filters} />}
      {tab === 3 && <IntegrityTab />}
      <ExportReportDialog open={exportOpen} onClose={() => setExportOpen(false)} codes={["B-01", "R-05", "R-10"]}
        title="Exportar la bitácora"
        filters={{
          user_email: filters.user_email, module_code: filters.module_code, event_type: filters.event_type,
          result: filters.result, date_from: filters.from, date_to: filters.to,
        }} />
    </Box>
  );
}

function FiltersBar({ filters, onChange }: { filters: Filters; onChange(f: Filters): void }) {
  const set = (k: keyof Filters) => (e: React.ChangeEvent<HTMLInputElement>) => onChange({ ...filters, [k]: e.target.value });
  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 3 }}>
          <TextField label="Usuario (correo)" value={filters.user_email} onChange={set("user_email")} />
        </Grid>
        <Grid size={{ xs: 6, md: 2 }}>
          <TextField select label="Módulo" value={filters.module_code} onChange={set("module_code")}>
            <MenuItem value="">Todos</MenuItem>
            {MODULE_OPTIONS.map((m) => <MenuItem key={m} value={m}>{moduleLabel(m)}</MenuItem>)}
          </TextField>
        </Grid>
        <Grid size={{ xs: 6, md: 2 }}>
          <TextField select label="Evento" value={filters.event_type} onChange={set("event_type")}>
            <MenuItem value="">Todos</MenuItem>
            {Object.entries(EVENT_LABELS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
          </TextField>
        </Grid>
        <Grid size={{ xs: 4, md: 1.5 }}>
          <TextField select label="Resultado" value={filters.result} onChange={set("result")}>
            <MenuItem value="">Todos</MenuItem>
            <MenuItem value="exito">Éxito</MenuItem>
            <MenuItem value="fallo">Fallo</MenuItem>
          </TextField>
        </Grid>
        <Grid size={{ xs: 4, md: 1.75 }}>
          <TextField label="Desde" type="date" value={filters.from} onChange={set("from")} slotProps={{ inputLabel: { shrink: true } }} />
        </Grid>
        <Grid size={{ xs: 4, md: 1.75 }}>
          <TextField label="Hasta" type="date" value={filters.to} onChange={set("to")} slotProps={{ inputLabel: { shrink: true } }} />
        </Grid>
      </Grid>
    </Paper>
  );
}

function RecordsTab({ filters }: { filters: Filters }) {
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(50);
  const [open, setOpen] = useState<number | null>(null);
  const q = useQuery({
    queryKey: ["audit", filters, page, size],
    queryFn: () => api<Page<AuditEntry>>("/audit", { query: { ...toQuery(filters), page: page + 1, size } }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <ErrorAlert error={q.error} />
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label="Registros de la bitácora">
          <TableHead>
            <TableRow>
              <TableCell />
              <TableCell>N.º</TableCell>
              <TableCell>Fecha y hora</TableCell>
              <TableCell>Usuario</TableCell>
              <TableCell>Módulo</TableCell>
              <TableCell>Evento</TableCell>
              <TableCell>Acción</TableCell>
              <TableCell>Resultado</TableCell>
              <TableCell>Duración</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {q.data?.items.map((e) => (
              <Fragment key={e.id}>
                <TableRow hover>
                  <TableCell padding="checkbox">
                    <IconButton size="small" aria-label={open === e.id ? "Ocultar detalle" : "Ver detalle"} aria-expanded={open === e.id}
                      onClick={() => setOpen(open === e.id ? null : e.id)}>
                      {open === e.id ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
                    </IconButton>
                  </TableCell>
                  <TableCell>{e.seq}</TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDateTime(e.occurred_at)}</TableCell>
                  <TableCell>
                    {e.user_email ?? "—"}
                    {e.role_code && <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>{e.role_code}</Typography>}
                  </TableCell>
                  <TableCell>{moduleLabel(e.module_code)}</TableCell>
                  <TableCell>{EVENT_LABELS[e.event_type] ?? e.event_type}</TableCell>
                  <TableCell>{e.action ?? "—"}</TableCell>
                  <TableCell>
                    <Chip size="small" label={e.result === "exito" ? "Éxito" : "Fallo"} color={e.result === "exito" ? "success" : "error"} variant="outlined" />
                  </TableCell>
                  <TableCell>{formatDuration(e.duration_ms)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell colSpan={9} sx={{ py: 0, borderBottom: open === e.id ? undefined : "none" }}>
                    <Collapse in={open === e.id} unmountOnExit>
                      <EntryDetail e={e} />
                    </Collapse>
                  </TableCell>
                </TableRow>
              </Fragment>
            ))}
            {q.data?.items.length === 0 && <TableRow><TableCell colSpan={9} align="center">Sin registros</TableCell></TableRow>}
          </TableBody>
        </Table>
        <TablePagination component="div" count={q.data?.total ?? 0} page={page} rowsPerPage={size}
          onPageChange={(_, p) => setPage(p)} onRowsPerPageChange={(ev) => { setSize(Number(ev.target.value)); setPage(0); }}
          rowsPerPageOptions={[25, 50, 100, 200]} />
      </TableContainer>
    </>
  );
}

function EntryDetail({ e }: { e: AuditEntry }) {
  const json = (v: unknown) => (v === null || v === undefined ? "—" : JSON.stringify(v, null, 2));
  return (
    <Box sx={{ p: 2, display: "grid", gap: 2, gridTemplateColumns: { lg: "minmax(0, 1fr) minmax(0, 1fr)" } }}>
      <Box>
        <Typography variant="caption" color="text.secondary">Endpoint</Typography>
        <Typography variant="body2">{e.http_method} {e.endpoint ?? "—"}</Typography>
        <Typography variant="caption" color="text.secondary">Entidad</Typography>
        <Typography variant="body2">{e.entity_type ?? "—"} {e.entity_id ?? ""}</Typography>
        {e.error_detail && (<><Typography variant="caption" color="text.secondary">Detalle del fallo</Typography><Typography variant="body2">{e.error_detail}</Typography></>)}
        <Typography variant="caption" color="text.secondary">IP</Typography>
        <Typography variant="body2">{e.ip ?? "—"}</Typography>
        <Typography variant="caption" color="text.secondary">User-agent</Typography>
        <Typography variant="body2" sx={{ wordBreak: "break-all" }}>{e.user_agent ?? "—"}</Typography>
        <Typography variant="caption" color="text.secondary">Hash</Typography>
        <Typography variant="body2" sx={{ fontFamily: "monospace", wordBreak: "break-all" }}>{e.hash}</Typography>
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: 1 }}>
        <Box>
          <Typography variant="caption" color="text.secondary">Antes</Typography>
          <pre className="json">{json(e.before)}</pre>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Después</Typography>
          <pre className="json">{json(e.after)}</pre>
        </Box>
      </Box>
    </Box>
  );
}

function TimelineTab({ filters }: { filters: Filters }) {
  const email = filters.user_email.trim();
  const q = useQuery({
    queryKey: ["audit-timeline", filters],
    queryFn: () => api<Page<AuditEntry>>("/audit", { query: { ...toQuery(filters), order: "asc", size: 200 } }),
    enabled: email.length > 3,
  });
  if (email.length <= 3) return <Alert severity="info">Escriba el correo de un usuario en el filtro para ver su línea de tiempo.</Alert>;
  const sessions = new Map<string, AuditEntry[]>();
  q.data?.items.forEach((e) => {
    const k = e.session_id ?? "sin-sesion";
    sessions.set(k, [...(sessions.get(k) ?? []), e]);
  });
  return (
    <Box>
      <ErrorAlert error={q.error} />
      {q.data && q.data.total > q.data.items.length && (
        <Alert severity="warning" sx={{ mb: 2 }}>Se muestran los primeros 200 eventos; acote el rango de fechas.</Alert>
      )}
      {[...sessions.entries()].map(([sid, events]) => (
        <Paper key={sid} variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="h3" gutterBottom>
            {sid === "sin-sesion" ? "Eventos fuera de sesión" : `Sesión iniciada ${formatDateTime(events[0].occurred_at)}`}
          </Typography>
          <Box component="ol" sx={{ listStyle: "none", pl: 0, m: 0, borderLeft: 2, borderColor: "primary.light" }}>
            {events.map((e) => (
              <Box component="li" key={e.id} sx={{ pl: 2, py: 0.75, position: "relative" }}>
                <Typography variant="body2">
                  <strong>{formatDateTime(e.occurred_at)}</strong> · {EVENT_LABELS[e.event_type] ?? e.event_type}
                  {e.module_code && ` · ${moduleLabel(e.module_code)}`}
                  {e.action && e.event_type === "accion" && ` · ${e.action}`}
                  {e.duration_ms !== null && ` · permanencia ${formatDuration(e.duration_ms)}`}
                  {e.result === "fallo" && " · FALLO"}
                </Typography>
              </Box>
            ))}
          </Box>
        </Paper>
      ))}
      {q.data?.items.length === 0 && <Alert severity="info">Sin eventos para ese usuario.</Alert>}
    </Box>
  );
}

function ModuleTimeTab({ filters }: { filters: Filters }) {
  const tq = toQuery(filters);
  const q = useQuery({
    queryKey: ["audit-module-time", filters],
    queryFn: () => api<ModuleTime[]>("/audit/module-time", { query: { user_email: tq.user_email, date_from: tq.date_from, date_to: tq.date_to } }),
  });
  return (
    <>
      <ErrorAlert error={q.error} />
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Suma de las permanencias registradas al salir de cada módulo{filters.user_email ? " para el usuario indicado (correo exacto)" : ""}.
      </Typography>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" aria-label="Permanencia por módulo">
          <TableHead>
            <TableRow>
              <TableCell>Módulo</TableCell>
              <TableCell align="right">Visitas</TableCell>
              <TableCell align="right">Tiempo total</TableCell>
              <TableCell align="right">Promedio por visita</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {q.data?.map((r) => (
              <TableRow key={r.module_code}>
                <TableCell>{moduleLabel(r.module_code)}</TableCell>
                <TableCell align="right">{r.visitas}</TableCell>
                <TableCell align="right">{formatDuration(r.total_ms)}</TableCell>
                <TableCell align="right">{formatDuration(r.visitas ? r.total_ms / r.visitas : 0)}</TableCell>
              </TableRow>
            ))}
            {q.data?.length === 0 && <TableRow><TableCell colSpan={4} align="center">Sin datos</TableCell></TableRow>}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}

function IntegrityTab() {
  const verify = useMutation({ mutationFn: () => api<VerifyResult>("/audit/verify") });
  const r = verify.data;
  return (
    <Paper variant="outlined" sx={{ p: 3, maxWidth: 760 }}>
      <Typography variant="body2" sx={{ mb: 2 }}>
        Cada registro guarda el hash SHA-256 del anterior. La verificación recalcula toda la cadena y detecta cualquier
        registro modificado o eliminado. La base de datos además impide UPDATE, DELETE y TRUNCATE sobre la bitácora.
      </Typography>
      <Button variant="contained" startIcon={<VerifiedIcon />} onClick={() => verify.mutate()} disabled={verify.isPending}>
        {verify.isPending ? "Verificando…" : "Verificar integridad"}
      </Button>
      <Box sx={{ mt: 2 }}>
        <ErrorAlert error={verify.error} />
        {r && (r.ok ? (
          <Alert severity="success">
            Cadena íntegra: {r.total_registros} registros verificados ({formatDateTime(r.verificado_en)}). Último hash:{" "}
            <code>{r.ultimo?.hash.slice(0, 16)}…</code>
          </Alert>
        ) : (
          <Alert severity="error">
            Se detectó una alteración en el registro N.º {r.primer_registro_alterado?.seq} ({r.primer_registro_alterado?.motivo === "contenido_alterado" ? "contenido modificado" : "cadena rota: falta o se reordenó un registro"}).
          </Alert>
        ))}
      </Box>
    </Paper>
  );
}
