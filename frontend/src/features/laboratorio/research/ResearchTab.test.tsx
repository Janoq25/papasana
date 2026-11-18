import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import actualReport from "../../../test/fixtures/training-report.json";
import { api } from "../../../api/client";
import ResearchTab from "./ResearchTab";
import { MethodologyFigure } from "./ResearchCharts";
import type { ResearchReport } from "./types";
vi.mock("../../../api/client", async (original) => ({ ...await original<typeof import("../../../api/client")>(), api: vi.fn() }));
function mount() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ResearchTab /></QueryClientProvider>);
}
beforeEach(() => {
  vi.mocked(api).mockReset().mockImplementation(async (path) => path === "/laboratorio/publicaciones"
    ? [{ id: actualReport.id, title: actualReport.title, trained_on: actualReport.trained_on, model_count: 4 }] : actualReport);
});
describe("resultados para el artículo", () => {
  it("presenta resultados reales y el contexto de las clases externas", async () => {
    mount();
    expect(await screen.findByRole("heading", { name: "Resultados para el artículo" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Comparación de los modelos entrenados" });
    expect(within(table).getAllByRole("row")).toHaveLength(5);
    expect(within(table).getByText("EfficientViT-B1")).toBeInTheDocument();
    expect(screen.getByText(/PlantDoc ya fue observado/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exportar F1 por arquitectura a 600 DPI" })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Copiar Comparación de los modelos/ })).toBeEnabled();
  });
  it("muestra la metodología ejecutada y distingue lo pendiente", async () => {
    mount(); await screen.findByRole("heading", { name: "Resultados para el artículo" });
    await userEvent.click(screen.getByRole("tab", { name: "Datos y metodología" }));
    expect(screen.getByRole("img", { name: "PapaSana · metodología ejecutada" })).toBeInTheDocument();
    expect(screen.getByText(/Validación anidada y evaluación prospectiva: pendientes/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exportar Metodología de la investigación a 600 DPI" })).toBeEnabled();
  });
  it("permite cambiar modelo y partición y muestra métricas y curvas guardadas", async () => {
    mount(); await screen.findByRole("heading", { name: "Resultados para el artículo" });
    await userEvent.click(screen.getByRole("tab", { name: "Detalle por modelo" }));
    expect(screen.getByRole("combobox", { name: "Modelo del entrenamiento" })).toBeInTheDocument();
    const set = screen.getByRole("combobox", { name: "Conjunto de evaluación" });
    await userEvent.click(set);
    await userEvent.click(screen.getByRole("option", { name: "PlantDoc · evaluación descriptiva" }));
    expect(screen.getByRole("table", { name: "Métricas por clase · ResNet50" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Matriz de confusión · ResNet50" })).toBeInTheDocument();
  });
  it("la metodología refleja los parámetros del informe en vez de cifras fijas", () => {
    const report = structuredClone(actualReport) as unknown as ResearchReport;
    report.models.forEach((m) => { m.img_size = 256; m.train.batch_size = 8; m.train.accumulation_steps = 1; m.train.epochs = 8; });
    render(<MethodologyFigure report={report} />);
    expect(screen.getByText("256 px · AdamW · CUDA · lote nominal 8")).toBeInTheDocument();
    expect(screen.getByText(/Hasta 8 épocas/)).toBeInTheDocument();
  });
  it("ofrece estado vacío si no hay informes publicados", async () => {
    vi.mocked(api).mockResolvedValue([]); mount();
    expect(await screen.findByText(/Todavía no hay informes/)).toBeInTheDocument();
  });
  it("ofrece reintento ante error de carga", async () => {
    vi.mocked(api).mockRejectedValue(new Error("Sin conexión")); mount();
    expect(await screen.findByRole("button", { name: "Reintentar cargar resultados" })).toBeInTheDocument();
  });
});
