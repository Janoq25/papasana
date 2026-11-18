import type { SvgIconComponent } from "@mui/icons-material";
import AssessmentIcon from "@mui/icons-material/Assessment";
import BiotechIcon from "@mui/icons-material/Biotech";
import CameraAltIcon from "@mui/icons-material/CameraAlt";
import DashboardIcon from "@mui/icons-material/Dashboard";
import DatasetIcon from "@mui/icons-material/Dataset";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import GrassIcon from "@mui/icons-material/Grass";
import HistoryEduIcon from "@mui/icons-material/HistoryEdu";
import LibraryBooksIcon from "@mui/icons-material/LibraryBooks";
import ListAltIcon from "@mui/icons-material/ListAlt";
import PeopleIcon from "@mui/icons-material/People";
import SettingsIcon from "@mui/icons-material/Settings";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import ThunderstormIcon from "@mui/icons-material/Thunderstorm";
import VpnKeyIcon from "@mui/icons-material/VpnKey";

export interface MenuItemDef {
  module: string;
  label: string;
  path: string;
  icon: SvgIconComponent;
  /** Permiso requerido para ver el ítem (null = cualquier usuario autenticado) */
  permission: string | null;
  /** Fase del plan en la que se implementa (las posteriores muestran "Próximamente") */
  phase: number;
  group: "operacion" | "analisis" | "administracion";
}

export const CURRENT_PHASE = 4;

export const MENU: MenuItemDef[] = [
  { module: "dashboard", label: "Dashboard", path: "/dashboard", icon: DashboardIcon, permission: "dashboard:ver", phase: 3, group: "operacion" },
  { module: "parcelas", label: "Parcelas", path: "/parcelas", icon: GrassIcon, permission: "parcelas:ver", phase: 2, group: "operacion" },
  { module: "diagnostico", label: "Captura y diagnóstico", path: "/diagnostico", icon: CameraAltIcon, permission: "diagnostico:ver", phase: 2, group: "operacion" },
  { module: "validacion", label: "Validación por experto", path: "/validacion", icon: FactCheckIcon, permission: "validacion:ver", phase: 2, group: "operacion" },
  { module: "alertas", label: "Riesgo y alertas", path: "/alertas", icon: ThunderstormIcon, permission: "alertas:ver", phase: 5, group: "operacion" },
  { module: "asistente", label: "Asistente IA", path: "/asistente", icon: SmartToyIcon, permission: "asistente:ver", phase: 6, group: "operacion" },
  { module: "reportes", label: "Reportes", path: "/reportes", icon: AssessmentIcon, permission: "reportes:ver", phase: 3, group: "analisis" },
  { module: "laboratorio", label: "Laboratorio de modelos", path: "/laboratorio", icon: BiotechIcon, permission: "laboratorio:ver", phase: 4, group: "analisis" },
  { module: "datasets", label: "Datasets y licencias", path: "/datasets", icon: DatasetIcon, permission: "datasets:ver", phase: 4, group: "analisis" },
  { module: "base_documental", label: "Base documental", path: "/base-documental", icon: LibraryBooksIcon, permission: "base_documental:ver", phase: 6, group: "analisis" },
  { module: "catalogos", label: "Catálogos", path: "/catalogos", icon: ListAltIcon, permission: "catalogos:ver", phase: 2, group: "administracion" },
  { module: "usuarios", label: "Usuarios", path: "/usuarios", icon: PeopleIcon, permission: "usuarios:ver", phase: 1, group: "administracion" },
  { module: "usuarios", label: "Roles y permisos", path: "/roles", icon: VpnKeyIcon, permission: "usuarios:ver", phase: 1, group: "administracion" },
  { module: "bitacora", label: "Bitácora", path: "/bitacora", icon: HistoryEduIcon, permission: "bitacora:ver", phase: 1, group: "administracion" },
  { module: "configuracion", label: "Configuración", path: "/configuracion", icon: SettingsIcon, permission: "configuracion:ver", phase: 1, group: "administracion" },
];

export const GROUP_LABELS: Record<MenuItemDef["group"], string> = {
  operacion: "Operación",
  analisis: "Análisis",
  administracion: "Administración",
};

/** Módulo de bitácora correspondiente a una ruta. */
export function moduleForPath(pathname: string): string {
  if (pathname.startsWith("/perfil")) return "perfil";
  if (pathname.startsWith("/notificaciones")) return "notificaciones";
  const item = MENU.find((m) => pathname === m.path || pathname.startsWith(m.path + "/"));
  return item?.module ?? "dashboard";
}

export function moduleLabel(code: string | null): string {
  if (!code) return "—";
  const extra: Record<string, string> = { perfil: "Mi perfil", auth: "Autenticación", notificaciones: "Notificaciones" };
  return extra[code] ?? MENU.find((m) => m.module === code)?.label ?? code;
}

/** Prioridad de la página de inicio (D-28): el Dashboard; si no, la Bitácora (Auditor); luego el orden del menú. */
const HOME_PRIORITY = ["/dashboard", "/bitacora"];

/** Página de inicio según el rol: el primer módulo permitido ya implementado; si no hay, el primero permitido. */
export function homePath(permissions: string[]): string {
  const rank = (path: string) => (HOME_PRIORITY.includes(path) ? HOME_PRIORITY.indexOf(path) : HOME_PRIORITY.length);
  const ordered = [...MENU].sort((a, b) => rank(a.path) - rank(b.path));
  const allowed = ordered.filter((m) => m.permission === null || permissions.includes(m.permission));
  const first = allowed.find((m) => m.phase <= CURRENT_PHASE) ?? allowed[0];
  return first?.path ?? "/perfil";
}
