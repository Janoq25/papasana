import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Box,
  Button,
  Chip,
  FormControlLabel,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Paper,
  Switch,
  TablePagination,
} from "@mui/material";
import { api } from "../../api/client";
import type { NotificationPage } from "../../api/types";
import ErrorAlert from "../../components/ErrorAlert";
import PageHeader from "../../components/PageHeader";
import { formatDateTime } from "../../utils/format";
import { KIND_LABELS, useMarkAllRead, useMarkRead } from "./useNotifications";

export default function NotificationsPage() {
  const navigate = useNavigate();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();
  const q = useQuery({
    queryKey: ["notificaciones", "lista", unreadOnly, page, size],
    queryFn: () => api<NotificationPage>("/notificaciones", { query: { unread_only: unreadOnly, page: page + 1, size } }),
    placeholderData: keepPreviousData,
  });

  return (
    <Box>
      <PageHeader title="Notificaciones" subtitle="Avisos internos: reportes listos y casos pendientes de validación."
        actions={
          <Button variant="outlined" disabled={!q.data?.unread || markAll.isPending} onClick={() => markAll.mutate()}>
            Marcar todas como leídas
          </Button>
        } />
      <FormControlLabel sx={{ mb: 1 }} label="Solo no leídas"
        control={<Switch checked={unreadOnly} onChange={(e) => { setUnreadOnly(e.target.checked); setPage(0); }} />} />
      <ErrorAlert error={q.error ?? markRead.error} />
      <Paper variant="outlined">
        <List aria-label="Lista de notificaciones">
          {q.data?.items.length === 0 && <ListItem><ListItemText primary="No hay notificaciones." /></ListItem>}
          {q.data?.items.map((n) => (
            <ListItemButton key={n.id} divider onClick={() => {
              if (!n.read_at) markRead.mutate(n.id);
              if (n.link) navigate(n.link);
            }}>
              <ListItemText
                primary={<Box component="span" sx={{ fontWeight: n.read_at ? 400 : 700 }}>{n.title}</Box>}
                secondary={`${n.body ? n.body + " · " : ""}${formatDateTime(n.created_at)}`} />
              <Chip size="small" variant="outlined" label={KIND_LABELS[n.kind] ?? n.kind} sx={{ ml: 1 }} />
              {!n.read_at && <Chip size="small" color="primary" label="Nueva" sx={{ ml: 1 }} />}
            </ListItemButton>
          ))}
        </List>
        <TablePagination component="div" count={q.data?.total ?? 0} page={page} rowsPerPage={size}
          rowsPerPageOptions={[20, 50]} onPageChange={(_, p) => setPage(p)}
          onRowsPerPageChange={(e) => { setSize(Number(e.target.value)); setPage(0); }} />
      </Paper>
    </Box>
  );
}
