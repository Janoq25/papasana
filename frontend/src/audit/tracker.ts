/**
 * Registro de entrada y salida de módulos para la bitácora.
 *
 * - Cambio de ruta  → salida (navegacion) del módulo anterior + entrada al nuevo.
 * - Pestaña oculta  → salida por sendBeacon (pestana_oculta); al volver, nueva entrada.
 * - Cierre (pagehide) → salida por sendBeacon (cierre).
 * - Logout / inactividad → salida con ese motivo antes de cerrar la sesión.
 *
 * El backend calcula la duración a partir de la hora de entrada; la salida es idempotente.
 */
import { api, beacon } from "../api/client";

export type ExitReason = "navegacion" | "pestana_oculta" | "cierre" | "logout" | "inactividad";

export interface ModuleEvent {
  module_code: string;
  event: "entrada" | "salida";
  entry_event_id?: number;
  reason?: ExitReason;
}

export interface Transport {
  post(ev: ModuleEvent): Promise<{ event_id: number }>;
  beacon(ev: ModuleEvent): boolean;
}

interface Current {
  module: string;
  entry: Promise<number | null>;
  id: number | null;
}

export class ModuleTracker {
  private current: Current | null = null;
  private suspended: string | null = null;

  constructor(private transport: Transport) {}

  get currentModule(): string | null {
    return this.current?.module ?? null;
  }

  enter(module: string): void {
    if (this.current?.module === module) return;
    void this.exit("navegacion");
    this.suspended = null;
    const cur: Current = { module, entry: Promise.resolve(null), id: null };
    cur.entry = this.transport
      .post({ module_code: module, event: "entrada" })
      .then((r) => {
        cur.id = r.event_id;
        return r.event_id;
      })
      .catch(() => null);
    this.current = cur;
  }

  async exit(reason: ExitReason, opts: { useBeacon?: boolean } = {}): Promise<void> {
    const cur = this.current;
    if (!cur) return;
    this.current = null;
    if (opts.useBeacon) {
      if (cur.id !== null) {
        this.transport.beacon({ module_code: cur.module, event: "salida", entry_event_id: cur.id, reason });
      }
      return;
    }
    const id = await cur.entry;
    if (id === null) return;
    try {
      await this.transport.post({ module_code: cur.module, event: "salida", entry_event_id: id, reason });
    } catch {
      /* la bitácora no debe bloquear la navegación */
    }
  }

  /** Pestaña oculta o cierre: registra la salida con beacon y recuerda el módulo para reanudar. */
  suspend(reason: ExitReason): void {
    if (!this.current) return;
    this.suspended = this.current.module;
    void this.exit(reason, { useBeacon: true });
  }

  resume(): void {
    if (this.suspended && !this.current) this.enter(this.suspended);
  }

  reset(): void {
    this.current = null;
    this.suspended = null;
  }
}

export const tracker = new ModuleTracker({
  post: (ev) => api<{ event_id: number }>("/audit/module-events", { method: "POST", body: ev }),
  beacon: (ev) => beacon("/audit/beacon", ev),
});
