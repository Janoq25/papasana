import { useEffect, useState } from "react";
import { Link as RouterLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  AppBar,
  Box,
  Chip,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { useAuth } from "../auth/AuthContext";
import { useIdleLogout } from "../auth/useIdleLogout";
import { tracker } from "../audit/tracker";
import NotificationBell from "./NotificationBell";
import UserAvatar from "./UserAvatar";
import { CURRENT_PHASE, GROUP_LABELS, MENU, moduleForPath, type MenuItemDef } from "../app/modules";

const DRAWER_WIDTH = 264;

function useModuleTracking() {
  const location = useLocation();
  useEffect(() => {
    tracker.enter(moduleForPath(location.pathname));
  }, [location.pathname]);

  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === "hidden") tracker.suspend("pestana_oculta");
      else tracker.resume();
    };
    const onPageHide = () => tracker.suspend("cierre");
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, []);
}

export default function AppLayout() {
  const { user, can, logout, photoVersion } = useAuth();
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up("md"));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const location = useLocation();
  const navigate = useNavigate();

  useModuleTracking();
  useIdleLogout(user?.session_settings.minutos_inactividad, () => void logout("inactividad"));

  const visible = MENU.filter((m) => m.permission === null || can(m.permission));
  const groups = (Object.keys(GROUP_LABELS) as MenuItemDef["group"][])
    .map((g) => ({ g, items: visible.filter((m) => m.group === g) }))
    .filter((x) => x.items.length > 0);

  const drawer = (
    <Box component="nav" aria-label="Menú principal">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ fontWeight: 700, color: "primary.main" }}>
          PapaSana AP-01
        </Typography>
      </Toolbar>
      <Divider />
      {groups.map(({ g, items }) => (
        <List key={g} dense subheader={<ListSubheader component="div">{GROUP_LABELS[g]}</ListSubheader>}>
          {items.map((m) => {
            const Icon = m.icon;
            const selected = location.pathname.startsWith(m.path);
            return (
              <ListItemButton
                key={m.path}
                component={RouterLink}
                to={m.path}
                selected={selected}
                aria-current={selected ? "page" : undefined}
                onClick={() => setMobileOpen(false)}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>
                  <Icon fontSize="small" />
                </ListItemIcon>
                <ListItemText primary={m.label} />
                {m.phase > CURRENT_PHASE && (
                  <Chip size="small" variant="outlined" label={`F${m.phase}`} aria-label={`Disponible en la fase ${m.phase}`} />
                )}
              </ListItemButton>
            );
          })}
        </List>
      ))}
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <a href="#contenido" className="skip-link">
        Saltar al contenido
      </a>
      <AppBar position="fixed" color="inherit" elevation={0}
        sx={{ borderBottom: 1, borderColor: "divider", ml: { md: `${DRAWER_WIDTH}px` }, width: { md: `calc(100% - ${DRAWER_WIDTH}px)` } }}>
        <Toolbar>
          {!desktop && (
            <IconButton edge="start" aria-label="Abrir menú" onClick={() => setMobileOpen(true)} sx={{ mr: 1 }}>
              <MenuIcon />
            </IconButton>
          )}
          <Typography variant="subtitle1" component="div" sx={{ flexGrow: 1 }} noWrap>
            {user?.session_settings.institucion}
          </Typography>
          <Chip label="Prototipo de investigación" color="warning" variant="outlined" size="small" sx={{ mr: 2, display: { xs: "none", sm: "flex" } }} />
          <NotificationBell />
          <Tooltip title="Cuenta">
            <IconButton onClick={(e) => setAnchor(e.currentTarget)} aria-label="Menú de la cuenta" aria-haspopup="menu">
              {user && (
                <UserAvatar userId={user.id} name={user.full_name} hasPhoto={user.has_photo}
                  version={photoVersion} sx={{ width: 34, height: 34, fontSize: 14 }} />
              )}
            </IconButton>
          </Tooltip>
          <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}>
            <Box sx={{ px: 2, py: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>{user?.full_name}</Typography>
              <Typography variant="caption" color="text.secondary">{user?.role.name}</Typography>
            </Box>
            <Divider />
            <MenuItem onClick={() => { setAnchor(null); navigate("/perfil"); }}>Mi perfil</MenuItem>
            <MenuItem onClick={() => { setAnchor(null); void logout("logout"); }}>Cerrar sesión</MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      <Box sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        {desktop ? (
          <Drawer variant="permanent" open sx={{ "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box" } }}>
            {drawer}
          </Drawer>
        ) : (
          <Drawer variant="temporary" open={mobileOpen} onClose={() => setMobileOpen(false)} ModalProps={{ keepMounted: true }}
            sx={{ "& .MuiDrawer-paper": { width: DRAWER_WIDTH } }}>
            {drawer}
          </Drawer>
        )}
      </Box>

      <Box component="main" id="contenido" tabIndex={-1} sx={{ flexGrow: 1, minWidth: 0, p: { xs: 2, md: 3 }, width: { xs: "100%", md: `calc(100% - ${DRAWER_WIDTH}px)` } }}>
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
