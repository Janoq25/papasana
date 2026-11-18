import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Diagnosis } from "../api/types";
import DiagnosisResult from "./DiagnosisResult";

vi.mock("../api/useAuthedObjectUrl", () => ({ useAuthedObjectUrl: () => ({ url: undefined, error: false }) }));

function diagnosis(overrides: Partial<Diagnosis> = {}): Diagnosis {
  return {
    id: "d1",
    created_at: "2026-11-04T15:00:00Z",
    status: "pendiente_revision",
    category: "sospechoso",
    category_label: "Sospechoso",
    predicted_class: "sano",
    probabilities: { sano: 0.55, sintomas_compatibles_tizon_tardio: 0.3, otra_enfermedad_foliar: 0.15 },
    confidence: 0.55,
    threshold_used: 0.7,
    requires_review: true,
    has_gradcam: true,
    inference_ms: 840,
    void_reason: null,
    model: { id: 1, model_key: "demo", display_name: "DEMO / no validado · ResNet50", architecture: "resnet50",
      stage: "demo", is_demo: true, label_scheme: "sintoma", classes: [] },
    parcel: { id: 1, code: "DEMO-JUN-001", name: "Parcela demo", region_code: "120000" },
    image: { id: "i1", original_filename: "hoja.jpg", width: 400, height: 300, size_bytes: 1000, captured_at: null,
      gps_source: "dispositivo", location: { lat: -12.2, lon: -75.1 }, inside_parcel: false, exif: {}, provenance: "web",
      duplicate_of_id: null, duplicate_distance: null },
    reviews: [],
    created_by: "u1",
    disclaimer: "Herramienta de apoyo a la decisión: requiere revisión profesional.",
    ...overrides,
  };
}

describe("DiagnosisResult", () => {
  it("muestra la franja DEMO, la categoría, la revisión requerida y el aviso profesional", () => {
    render(<DiagnosisResult diagnosis={diagnosis()} />);
    expect(screen.getByText(/DEMO \/ no validado\./)).toBeInTheDocument();
    expect(screen.getByText("Sospechoso")).toBeInTheDocument();
    expect(screen.getByText("Requiere revisión")).toBeInTheDocument();
    expect(screen.getAllByText("55.0 %")).toHaveLength(2); // confianza global y barra de la clase "Sano"
    expect(screen.getByText(/requiere revisión profesional/)).toBeInTheDocument();
    expect(screen.getByText(/fuera del polígono de la parcela/)).toBeInTheDocument();
  });

  it("no muestra la franja DEMO con un modelo validado y muestra la validación del especialista", () => {
    render(
      <DiagnosisResult
        diagnosis={diagnosis({
          model: { id: 2, model_key: "v1", display_name: "ConvNeXt v1", architecture: "convnext", stage: "production",
            is_demo: false, label_scheme: "sintoma", classes: [] },
          status: "validado",
          category: "tizon_tardio_compatible",
          requires_review: false,
          reviews: [{ id: 1, reviewer_id: "a", decision: "confirma", final_label: "tizon_tardio_confirmado",
            final_label_name: "Tizón tardío confirmado", evidence: "esporulacion", differential: null, notes: null,
            created_at: "2026-11-04T16:00:00Z" }],
        })}
      />,
    );
    expect(screen.queryByText(/DEMO \/ no validado\./)).not.toBeInTheDocument();
    expect(screen.getByText("Tizón tardío: síntomas compatibles")).toBeInTheDocument();
    expect(screen.getByText(/Tizón tardío confirmado/)).toBeInTheDocument();
  });
});
