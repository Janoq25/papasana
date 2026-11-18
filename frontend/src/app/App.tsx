import { lazy, Suspense } from "react";
import { Box, CircularProgress, CssBaseline, ThemeProvider } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ApiError } from "../api/client";
import { AuthProvider, useAuth } from "../auth/AuthContext";
import { RequirePermission } from "../auth/RequirePermission";
import AppLayout from "../components/AppLayout";
import { ForgotPasswordPage, ResetPasswordPage } from "../features/auth/PasswordRecoveryPages";
import LoginPage from "../features/auth/LoginPage";
import AuditPage from "../features/bitacora/AuditPage";
import CatalogsPage from "../features/catalogos/CatalogsPage";
import DatasetsPage from "../features/datasets/DatasetsPage";
import ComingSoonPage from "../features/common/ComingSoonPage";
import SettingsPage from "../features/configuracion/SettingsPage";
import DiagnosisPage from "../features/diagnostico/DiagnosisPage";
import NotificationsPage from "../features/notificaciones/NotificationsPage";
import ParcelsPage from "../features/parcelas/ParcelsPage";
import ProfilePage from "../features/perfil/ProfilePage";
import ReportsPage from "../features/reportes/ReportsPage";
import RolesPage from "../features/usuarios/RolesPage";
import UsersPage from "../features/usuarios/UsersPage";
import ValidationPage from "../features/validacion/ValidationPage";
import { CURRENT_PHASE, homePath, MENU } from "./modules";
import { theme } from "./theme";

// El dashboard (gráficos y mapa de calor) se carga bajo demanda para aligerar el paquete inicial.
const DashboardPage = lazy(() => import("../features/dashboard/DashboardPage"));
const LabPage = lazy(() => import("../features/laboratorio/LabPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
});

const IMPLEMENTED: Record<string, React.ReactNode> = {
  "/dashboard": (
    <Suspense fallback={<Loading />}>
      <DashboardPage />
    </Suspense>
  ),
  "/reportes": <ReportsPage />,
  "/laboratorio": (
    <Suspense fallback={<Loading />}>
      <LabPage />
    </Suspense>
  ),
  "/datasets": <DatasetsPage />,
  "/parcelas": <ParcelsPage />,
  "/diagnostico": <DiagnosisPage />,
  "/validacion": <ValidationPage />,
  "/catalogos": <CatalogsPage />,
  "/usuarios": <UsersPage />,
  "/roles": <RolesPage />,
  "/bitacora": <AuditPage />,
  "/configuracion": <SettingsPage />,
};

function Loading() {
  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }} role="status" aria-live="polite">
      <CircularProgress aria-label="Cargando" />
    </Box>
  );
}

function ProtectedArea() {
  const { status } = useAuth();
  if (status === "loading") return <Loading />;
  if (status === "anonymous") return <Navigate to="/login" replace />;
  return <AppLayout />;
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { status, user } = useAuth();
  if (status === "loading") return <Loading />;
  if (status === "authenticated" && user) return <Navigate to={homePath(user.permissions)} replace />;
  return <>{children}</>;
}

function Home() {
  const { user } = useAuth();
  return <Navigate to={homePath(user?.permissions ?? [])} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
      <Route path="/recuperar" element={<PublicOnly><ForgotPasswordPage /></PublicOnly>} />
      <Route path="/restablecer" element={<ResetPasswordPage />} />
      <Route element={<ProtectedArea />}>
        <Route index element={<Home />} />
        <Route path="/perfil" element={<ProfilePage />} />
        <Route path="/notificaciones" element={<NotificationsPage />} />
        {MENU.map((m) => (
          <Route
            key={m.path}
            path={m.path}
            element={
              <RequirePermission permission={m.permission}>
                {m.phase <= CURRENT_PHASE && IMPLEMENTED[m.path] ? (
                  IMPLEMENTED[m.path]
                ) : (
                  <ComingSoonPage title={m.label} module={m.module} phase={m.phase} />
                )}
              </RequirePermission>
            }
          />
        ))}
        <Route path="*" element={<Home />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
