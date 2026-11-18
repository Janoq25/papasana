import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ReportDefinition, ReportOptions } from "../../api/types";
import ReportForm from "./ReportForm";

const definition: ReportDefinition = {
  code: "R-01",
  title: "Diagnósticos por fecha, parcela y técnico",
  kind: "operacional",
  kind_label: "Operacional",
  description: "…",
  formats: ["pdf", "docx", "xlsx"],
  filters: [
    { key: "date_from", label: "Desde", type: "date" },
    { key: "date_to", label: "Hasta", type: "date" },
    { key: "parcel_id", label: "Parcela", type: "parcel" },
    { key: "category", label: "Categoría", type: "select", options: { sano: "Sano", sospechoso: "Sospechoso" } },
  ],
  available_from_phase: null,
};

const options: ReportOptions = {
  regions: [], varieties: [], technicians: [], model_versions: [], roles: [], modules: [],
  parcels: [{ id: 7, code: "DEMO-JUN-001", name: "Sicaya alta" }],
};

describe("ReportForm", () => {
  it("construye los campos del reporte y envía filtros limpios en el formato elegido", async () => {
    const onSubmit = vi.fn();
    render(<ReportForm definition={definition} options={options} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-01" } });
    await userEvent.click(screen.getByRole("combobox", { name: "Parcela" }));
    await userEvent.click(within(screen.getByRole("listbox")).getByText("DEMO-JUN-001 · Sicaya alta"));
    await userEvent.click(screen.getByRole("button", { name: "Excel" }));
    await userEvent.click(screen.getByRole("button", { name: "Generar reporte" }));
    expect(onSubmit).toHaveBeenCalledWith("xlsx", { date_from: "2026-10-01", parcel_id: 7 });
  });

  it("no envía un rango de fechas invertido", async () => {
    const onSubmit = vi.fn();
    render(<ReportForm definition={definition} options={options} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("Desde"), { target: { value: "2026-10-10" } });
    fireEvent.change(screen.getByLabelText("Hasta"), { target: { value: "2026-10-01" } });
    expect(screen.getByText(/posterior a la fecha inicial/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generar reporte" })).toBeDisabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("toma los filtros iniciales (p. ej., desde el dashboard) que el reporte admite", () => {
    render(<ReportForm definition={definition} options={options} onSubmit={vi.fn()}
      initial={{ date_from: "2026-09-01", region_code: "120000" }} />);
    expect(screen.getByLabelText("Desde")).toHaveValue("2026-09-01");
  });

  it("avisa cuando el reporte depende de una fase posterior", () => {
    render(<ReportForm definition={{ ...definition, available_from_phase: 5 }} options={options} onSubmit={vi.fn()} />);
    expect(screen.getByText(/Fase 5/)).toBeInTheDocument();
  });
});
