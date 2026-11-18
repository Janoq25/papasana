import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Box, Button, Divider, IconButton, Menu, MenuItem, Tooltip, Typography } from "@mui/material";
import NotificationsIcon from "@mui/icons-material/Notifications";
import type { AppNotification } from "../api/types";
import { useMarkAllRead, useMarkRead, useNotificationSummary } from "../features/notificaciones/useNotifications";
import { formatDateTime } from "../utils/format";

export default function NotificationBell() {
  const summary = useNotificationSummary();
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const unread = summary.data?.unread ?? 0;
  const label = unread ? `Notificaciones: ${unread} sin leer` : "Notificaciones";

  const open = (n: AppNotification) => {
    setAnchor(null);
    if (!n.read_at) markRead.mutate(n.id);
    if (n.link) navigate(n.link);
  };

  return (
    <>
      <Tooltip title="Notificaciones">
        <IconButton aria-label={label} aria-haspopup="menu" onClick={(e) => setAnchor(e.currentTarget)} sx={{ mr: 1 }}>
          <Badge badgeContent={unread} color="error" max={99}>
            <NotificationsIcon />
          </Badge>
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}
        slotProps={{ paper: { sx: { width: 360, maxWidth: "95vw" } } }}>
        <Box sx={{ px: 2, py: 1, display: "flex", alignItems: "center" }}>
          <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>Notificaciones</Typography>
          <Button size="small" disabled={!unread || markAll.isPending} onClick={() => markAll.mutate()}>
            Marcar todas como leídas
          </Button>
        </Box>
        <Divider />
        {(summary.data?.recent.length ?? 0) === 0 && (
          <MenuItem disabled>No tiene notificaciones.</MenuItem>
        )}
        {summary.data?.recent.map((n) => (
          <MenuItem key={n.id} onClick={() => open(n)} sx={{ whiteSpace: "normal", alignItems: "flex-start" }}>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: n.read_at ? 400 : 700 }}>
                {!n.read_at && <span className="visually-hidden">No leída: </span>}
                {n.title}
              </Typography>
              {n.body && <Typography variant="caption" color="text.secondary" component="div">{n.body}</Typography>}
              <Typography variant="caption" color="text.secondary">{formatDateTime(n.created_at)}</Typography>
            </Box>
          </MenuItem>
        ))}
        <Divider />
        <MenuItem onClick={() => { setAnchor(null); navigate("/notificaciones"); }}>Ver todas</MenuItem>
      </Menu>
    </>
  );
}
