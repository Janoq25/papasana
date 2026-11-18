import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NotificationBell from "./NotificationBell";

const api = vi.fn();
vi.mock("../api/client", () => ({ api: (...args: unknown[]) => api(...args) }));

const summary = {
  unread: 2,
  recent: [
    { id: 11, kind: "reporte_listo", title: "Reporte listo: R-01 (PDF)", body: "Diagnósticos", link: "/reportes",
      entity_type: "reporte", entity_id: "x", created_at: "2026-11-10T15:00:00Z", read_at: null },
    { id: 10, kind: "revision_pendiente", title: "Nuevo caso pendiente de validación", body: "Parcela DEMO-JUN-001",
      link: "/validacion", entity_type: "diagnostico", entity_id: "y", created_at: "2026-11-10T14:00:00Z",
      read_at: "2026-11-10T14:30:00Z" },
  ],
};

function renderBell() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<NotificationBell />} />
          <Route path="/reportes" element={<p>Página de reportes</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("NotificationBell", () => {
  beforeEach(() => {
    api.mockReset();
    api.mockImplementation((path: string) => Promise.resolve(path === "/notificaciones/resumen" ? summary : undefined));
  });

  it("consulta en segundo plano y muestra las no leídas", async () => {
    renderBell();
    expect(await screen.findByRole("button", { name: "Notificaciones: 2 sin leer" })).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/notificaciones/resumen", { background: true });
  });

  it("al abrir una notificación la marca como leída y navega a su enlace", async () => {
    renderBell();
    await userEvent.click(await screen.findByRole("button", { name: /2 sin leer/ }));
    await userEvent.click(screen.getByText("Reporte listo: R-01 (PDF)"));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/notificaciones/11/leida", { method: "POST" }));
    expect(await screen.findByText("Página de reportes")).toBeInTheDocument();
  });

  it("una notificación ya leída no se vuelve a marcar", async () => {
    renderBell();
    await userEvent.click(await screen.findByRole("button", { name: /2 sin leer/ }));
    await userEvent.click(screen.getByText("Nuevo caso pendiente de validación"));
    expect(api).not.toHaveBeenCalledWith("/notificaciones/10/leida", expect.anything());
  });
});
