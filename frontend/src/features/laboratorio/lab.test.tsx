import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { DatasetEntry, LabModel, Promotion } from "../../api/types";
import { FakeAuth } from "../../test/fakeAuth";
import { LicenseDialog } from "../datasets/DatasetsPage";
import { canPromote, canRollbackTo, fmtP, summarize } from "./labUtils";
import PromotionsTab from "./PromotionsTab";

vi.mock("../../api/client", () => ({ api: vi.fn().mockResolvedValue({}), downloadFile: vi.fn() }));

function model(over: Partial<LabModel> = {}): LabModel {
  return {
    id: 2, model_key: "papasana-resnet50:v1", architecture: "resnet50", display_name: "ResNet50 · papasana-resnet50 v1",
    source: "mlflow", stage: "staging", is_demo: false, smoke_test: false, label_scheme: "sintoma",
    classes: ["sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar"], temperature: 1.2,
    mlflow_model_name: "papasana-resnet50", mlflow_version: "1", mlflow_run_id: "r1", train_dataset_ids: [],
    metrics_summary: null, registered_at: null, synced_at: null, ...over,
  };
}

function promotion(over: Partial<Promotion> = {}): Promotion {
  return {
    id: 7, action: "promover", status: "pendiente", from_stage: "staging", to_stage: "production",
    model_version: model(), previous: null, requested_by: "u1", requested_by_name: "Teodoro Técnico",
    request_reason: "Mejor validación externa", decided_by: null, decided_by_name: null, decision_reason: null,
    error: null, created_at: "2026-11-12T15:00:00Z", decided_at: null, ...over,
  };
}

const wrap = (ui: React.ReactNode, permissions: string[]) => (
  <QueryClientProvider client={new QueryClient()}>
    <FakeAuth permissions={permissions}>{ui}</FakeAuth>
  </QueryClientProvider>
);

describe("utilidades del laboratorio", () => {
  it("solo muestra las métricas que existen en MLflow", () => {
    expect(summarize(model()).hasMetrics).toBe(false);
    const s = summarize(model({ metrics_summary: { val_macro_f1: 0.81, cv_mean_test_macro_f1: 0.79,
      cv_std_test_macro_f1: 0.02, external_plantdoc_papa_macro_f1: 0.55, external_plantdoc_papa_ece: 0.08 } }));
    expect(s).toMatchObject({ valF1: 0.81, cvF1: 0.79, cvF1Std: 0.02, extF1: 0.55, extName: "plantdoc_papa", ece: 0.08 });
  });

  it("reglas de promoción y rollback", () => {
    const demo = model({ id: 1, source: "demo", stage: "demo" });
    expect(canPromote(model())).toBe(true);
    expect(canPromote(demo)).toBe(false);
    expect(canPromote(model({ stage: "production" }))).toBe(false);
    expect(canRollbackTo(demo, [], true)).toBe(true);   // retirar el modelo entrenado
    expect(canRollbackTo(demo, [], false)).toBe(false); // el DEMO ya está en uso
    const archived = model({ id: 3, stage: "archived" });
    expect(canRollbackTo(archived, [], true)).toBe(false);
    expect(canRollbackTo(archived, [promotion({ status: "aplicada", previous: archived })], true)).toBe(true);
    expect(fmtP(0.0004)).toBe("< 0,001");
    expect(fmtP(0.0312)).toBe("0,031");
  });
});

describe("PromotionsTab (cuatro ojos)", () => {
  it("quien solicitó no ve el botón de aprobar", () => {
    render(wrap(<PromotionsTab promotions={[promotion({ requested_by: "u1" })]} />, ["laboratorio:aprobar"]));
    expect(screen.getByText("Su solicitud: la aprueba otra persona")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aprobar" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
  });

  it("otra persona con permiso puede aprobar o rechazar", async () => {
    render(wrap(<PromotionsTab promotions={[promotion({ requested_by: "otro" })]} />, ["laboratorio:aprobar"]));
    await userEvent.click(screen.getByRole("button", { name: "Aprobar" }));
    expect(screen.getByText(/se restaura el anterior/)).toBeInTheDocument();
  });

  it("sin permiso de aprobación no hay acciones", () => {
    render(wrap(<PromotionsTab promotions={[promotion({ requested_by: "otro" })]} />, ["laboratorio:ver"]));
    expect(screen.queryByRole("button", { name: "Aprobar" })).not.toBeInTheDocument();
  });
});

describe("LicenseDialog", () => {
  const ds: DatasetEntry = {
    id: 1, code: "plantdoc_papa", name: "PlantDoc", version: "2019", source_url: null, license: null, license_url: null,
    license_status: "por_verificar", license_notes: "Copias de terceros lo declaran CC BY 4.0", license_verified_by: null,
    license_verified_by_name: null, license_verified_at: null, citation: null, conditions: "campo", label_scheme: "sintoma",
    etiological_confirmation: "no", has_group_ids: false, role: "validacion_externa", class_map: {}, n_images: null,
    notes: null, is_active: true, usable: false, updated_at: "2026-11-12T00:00:00Z",
  };

  it("exige licencia, enlace oficial y descripción para verificar", async () => {
    render(wrap(<LicenseDialog dataset={ds} onClose={vi.fn()} />, ["datasets:editar"]));
    const submit = screen.getByRole("button", { name: "Registrar revisión" });
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Licencia \(p\. ej/), "CC BY 4.0");
    await userEvent.type(screen.getByLabelText(/Enlace a la licencia/), "https://github.com/pratikkayal/PlantDoc-Dataset");
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Qué revisó/), "Revisé el archivo LICENSE del repositorio");
    expect(submit).toBeEnabled();
    expect(screen.getByText(/Copias de terceros/)).toBeInTheDocument();
  });
});
