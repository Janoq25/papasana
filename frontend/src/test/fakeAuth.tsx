import type { ReactNode } from "react";
import { vi } from "vitest";
import { AuthContext } from "../auth/AuthContext";
import type { Me } from "../api/types";

export function fakeUser(permissions: string[]): Me {
  return {
    id: "u1",
    email: "tecnico@demo.papasana.pe",
    full_name: "Teodoro Técnico",
    institution: null,
    phone: null,
    region_code: "120000",
    role: { id: 4, code: "TECNICO", name: "Técnico de campo / Productor", data_scope: "propio" },
    is_active: true,
    is_locked: false,
    has_photo: false,
    locked_until: null,
    last_login_at: null,
    created_at: "2026-11-04T00:00:00Z",
    preferences: {},
    permissions,
    session_settings: { minutos_inactividad: 30, longitud_minima_contrasena: 10, institucion: "PapaSana", aviso: "" },
  };
}

export function FakeAuth({
  permissions = [],
  login = vi.fn(),
  children,
}: {
  permissions?: string[];
  login?: (email: string, password: string) => Promise<Me>;
  children: ReactNode;
}) {
  const user = fakeUser(permissions);
  return (
    <AuthContext.Provider
      value={{
        status: "authenticated",
        user,
        lastLogoutReason: null,
        login,
        logout: vi.fn(),
        reloadMe: vi.fn(),
        can: (p: string) => permissions.includes(p),
        photoVersion: 0,
        bumpPhoto: vi.fn(),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
