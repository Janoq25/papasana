import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { DashboardData } from "../../api/types";
import KpiGrid from "./KpiGrid";

const kpis: DashboardData["kpis"] = {
  diagnosticos: 40,
  diagnosticos_ejemplo: 40,
  por_categoria: [
    { categoria: "sano", etiqueta: "Sano", total: 20, porcentaje: 0.5 },
    { categoria: "sospechoso", etiqueta: "Sospechoso", total: 12, porcentaje: 0.3 },
    { categoria: "tizon_tardio_compatible", etiqueta: "Tizón tardío: síntomas compatibles", total: 8, porcentaje: 0.2 },
  ],
  pendientes_validacion: 5,
  parcelas: 4,
  parcelas_con_casos_compatibles: { valor: 2, dias: 14, hasta: "2026-11-10" },
  acuerdo_experto: { valor: 0.75, n: 8, confirma: 6, corrige: 2 },
  precision_modelo: { valor: null, motivo: "No hay un modelo en producción: el modelo en uso es DEMO / no validado." },
  alertas_activas: { valor: null, motivo: "Disponible con el módulo de riesgo climático (Fase 5)." },
  parcelas_en_riesgo: { valor: null, motivo: "Disponible con el módulo de riesgo climático (Fase 5)." },
};

describe("KpiGrid", () => {
  it("muestra los KPIs calculados y no inventa los que aún no existen", () => {
    render(<MemoryRouter><KpiGrid kpis={kpis} canValidate /></MemoryRouter>);
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("20.0 % del total")).toBeInTheDocument();
    expect(screen.getByText("2 de 4")).toBeInTheDocument();
    expect(screen.getByText("Últimos 14 días (hasta el 10/11/2026)")).toBeInTheDocument();
    expect(screen.getByText("75.0 %")).toBeInTheDocument();
    expect(screen.getByText("6 confirmados y 2 corregidos")).toBeInTheDocument();
    // Precisión, alertas y riesgo: sin valor, con el motivo
    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.getByText(/modelo en uso es DEMO/)).toBeInTheDocument();
    expect(screen.getAllByText(/Fase 5/)).toHaveLength(2);
    expect(screen.getByRole("link", { name: /bandeja de validación/ })).toHaveAttribute("href", "/validacion");
  });

  it("sin permiso de validación no ofrece el enlace a la bandeja", () => {
    render(<MemoryRouter><KpiGrid kpis={{ ...kpis, acuerdo_experto: { valor: null, n: 0, confirma: 0, corrige: 0 } }}
      canValidate={false} /></MemoryRouter>);
    expect(screen.queryByRole("link", { name: /bandeja/ })).not.toBeInTheDocument();
    expect(screen.getByText("Aún no hay casos revisados")).toBeInTheDocument();
  });
});
