import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, onUnauthorized, refreshSession, setAccessToken } from "../api/client";
import type { Me, TokenResponse } from "../api/types";
import { tracker } from "../audit/tracker";

type Status = "loading" | "authenticated" | "anonymous";
export type LogoutReason = "logout" | "inactividad" | "expirada";

interface AuthValue {
  status: Status;
  user: Me | null;
  /** Motivo del último cierre de sesión (para mostrar un aviso en el login) */
  lastLogoutReason: LogoutReason | null;
  login(email: string, password: string): Promise<Me>;
  logout(reason?: LogoutReason): Promise<void>;
  reloadMe(): Promise<void>;
  can(permission: string): boolean;
  /** Se incrementa al cambiar la foto de perfil para refrescar los avatares */
  photoVersion: number;
  bumpPhoto(): void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<Me | null>(null);
  const [lastLogoutReason, setLastLogoutReason] = useState<LogoutReason | null>(null);
  const [photoVersion, setPhotoVersion] = useState(0);
  const bumpPhoto = useCallback(() => setPhotoVersion((v) => v + 1), []);

  const clearLocal = useCallback(
    (reason: LogoutReason | null) => {
      tracker.reset();
      setAccessToken(null);
      setUser(null);
      setStatus("anonymous");
      setLastLogoutReason(reason);
      queryClient.clear();
    },
    [queryClient],
  );

  // Restaurar la sesión con la cookie de refresh al cargar la aplicación.
  useEffect(() => {
    let active = true;
    refreshSession().then((data) => {
      if (!active) return;
      if (data) {
        setUser(data.user);
        setStatus("authenticated");
      } else {
        setStatus("anonymous");
      }
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    onUnauthorized(() => clearLocal("expirada"));
    return () => onUnauthorized(null);
  }, [clearLocal]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<TokenResponse>("/auth/login", { method: "POST", body: { email, password } });
    setAccessToken(data.access_token);
    setUser(data.user);
    setLastLogoutReason(null);
    setStatus("authenticated");
    return data.user;
  }, []);

  const logout = useCallback(
    async (reason: LogoutReason = "logout") => {
      const apiReason = reason === "inactividad" ? "inactividad" : "logout";
      await tracker.exit(apiReason);
      try {
        await api("/auth/logout", { method: "POST", body: { reason: apiReason } });
      } catch {
        /* la sesión se cierra localmente aunque el servidor no responda */
      }
      clearLocal(reason);
    },
    [clearLocal],
  );

  const reloadMe = useCallback(async () => {
    setUser(await api<Me>("/auth/me"));
  }, []);

  const can = useCallback((permission: string) => !!user?.permissions.includes(permission), [user]);

  const value = useMemo(
    () => ({ status, user, lastLogoutReason, login, logout, reloadMe, can, photoVersion, bumpPhoto }),
    [status, user, lastLogoutReason, login, logout, reloadMe, can, photoVersion, bumpPhoto],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}

export { AuthContext };
