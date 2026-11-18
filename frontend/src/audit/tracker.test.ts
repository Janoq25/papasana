import { describe, expect, it, vi } from "vitest";
import { ModuleTracker, type ModuleEvent, type Transport } from "./tracker";

function fakeTransport() {
  let next = 100;
  const posts: ModuleEvent[] = [];
  const beacons: ModuleEvent[] = [];
  const transport: Transport = {
    post: vi.fn(async (ev: ModuleEvent) => {
      posts.push(ev);
      return { event_id: next++ };
    }),
    beacon: vi.fn((ev: ModuleEvent) => {
      beacons.push(ev);
      return true;
    }),
  };
  return { transport, posts, beacons };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("ModuleTracker", () => {
  it("registra la entrada y, al navegar, la salida del módulo anterior con su id", async () => {
    const { transport, posts } = fakeTransport();
    const t = new ModuleTracker(transport);
    t.enter("dashboard");
    await flush();
    t.enter("usuarios");
    await flush();
    expect(posts).toEqual([
      { module_code: "dashboard", event: "entrada" },
      { module_code: "usuarios", event: "entrada" },
      { module_code: "dashboard", event: "salida", entry_event_id: 100, reason: "navegacion" },
    ]);
    expect(t.currentModule).toBe("usuarios");
  });

  it("no duplica la entrada si la ruta cambia dentro del mismo módulo", async () => {
    const { transport, posts } = fakeTransport();
    const t = new ModuleTracker(transport);
    t.enter("usuarios");
    t.enter("usuarios");
    await flush();
    expect(posts).toHaveLength(1);
  });

  it("al ocultar la pestaña envía la salida por beacon y al volver registra una nueva entrada", async () => {
    const { transport, posts, beacons } = fakeTransport();
    const t = new ModuleTracker(transport);
    t.enter("bitacora");
    await flush();
    t.suspend("pestana_oculta");
    expect(beacons).toEqual([{ module_code: "bitacora", event: "salida", entry_event_id: 100, reason: "pestana_oculta" }]);
    expect(t.currentModule).toBeNull();
    t.resume();
    await flush();
    expect(posts.at(-1)).toEqual({ module_code: "bitacora", event: "entrada" });
  });

  it("el logout espera la entrada pendiente antes de registrar la salida", async () => {
    const { transport, posts } = fakeTransport();
    const t = new ModuleTracker(transport);
    t.enter("perfil"); // la entrada aún no respondió
    await t.exit("logout");
    expect(posts.at(-1)).toEqual({ module_code: "perfil", event: "salida", entry_event_id: 100, reason: "logout" });
  });

  it("si la entrada falló no intenta registrar la salida", async () => {
    const transport: Transport = { post: vi.fn().mockRejectedValueOnce(new Error("red")), beacon: vi.fn() };
    const t = new ModuleTracker(transport);
    t.enter("perfil");
    await t.exit("logout");
    expect(transport.post).toHaveBeenCalledTimes(1);
  });
});
