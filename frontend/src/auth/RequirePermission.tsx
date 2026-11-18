import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";
import ForbiddenPage from "../features/common/ForbiddenPage";

/**
 * Oculta la ruta o el elemento si el usuario no tiene el permiso.
 * Es solo una ayuda de interfaz: el backend valida siempre cada endpoint.
 */
export function RequirePermission({
  permission,
  children,
  fallback,
}: {
  permission: string | null;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { can } = useAuth();
  if (permission && !can(permission)) return <>{fallback ?? <ForbiddenPage />}</>;
  return <>{children}</>;
}

/** Variante para botones y acciones: no muestra nada si falta el permiso. */
export function Can({ permission, children }: { permission: string; children: ReactNode }) {
  return (
    <RequirePermission permission={permission} fallback={null}>
      {children}
    </RequirePermission>
  );
}
