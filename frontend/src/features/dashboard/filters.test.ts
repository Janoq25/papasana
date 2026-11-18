import dayjs from "dayjs";
import { describe, expect, it } from "vitest";
import { filenameFromDisposition } from "../../api/client";
import { cleanFilters } from "../reportes/useReports";
import { defaultFilters, filtersFromParams, filtersToParams, periodLabel, rangeError } from "./filters";

describe("filtros globales del dashboard", () => {
  const now = dayjs("2026-11-10T15:00:00Z");

  it("por defecto cubre los últimos 90 días en hora de Lima", () => {
    const d = defaultFilters(now);
    expect(d.date_to).toBe("2026-11-10");
    expect(d.date_from).toBe("2026-08-13");
    expect(d.region_code).toBe("");
  });

  it("usa la fecha de Lima aunque en UTC ya sea el día siguiente", () => {
    expect(defaultFilters(dayjs("2026-11-11T02:00:00Z")).date_to).toBe("2026-11-10");
  });

  it("guarda en la URL solo lo que difiere de los valores por defecto", () => {
    const defaults = defaultFilters(now);
    const params = filtersToParams({ ...defaults, region_code: "120000" }, defaults);
    expect(params).toEqual({ region_code: "120000" });
    const back = filtersFromParams(new URLSearchParams(params), defaults);
    expect(back).toEqual({ ...defaults, region_code: "120000" });
  });

  it("detecta un rango de fechas invertido", () => {
    expect(rangeError({ ...defaultFilters(now), date_from: "2026-11-10", date_to: "2026-11-01" })).toMatch(/posterior/);
    expect(rangeError(defaultFilters(now))).toBeNull();
  });

  it("formatea el periodo según la granularidad", () => {
    expect(periodLabel("2026-11-02", "dia")).toBe("02/11");
    expect(periodLabel("2026-11-02", "semana")).toBe("Sem. 02/11");
    expect(periodLabel("2026-11-01", "mes")).toMatch(/nov/i);
  });
});

describe("utilidades de reportes", () => {
  it("limpia los filtros vacíos, convierte los numéricos y descarta los no admitidos", () => {
    expect(cleanFilters({ parcel_id: "3", region_code: "", user_email: " a@b.pe ", otro: "x" },
      ["parcel_id", "region_code", "user_email"])).toEqual({ parcel_id: 3, user_email: "a@b.pe" });
  });

  it("lee el nombre del archivo de Content-Disposition (UTF-8 primero)", () => {
    expect(filenameFromDisposition(`attachment; filename="R-01_x.pdf"; filename*=UTF-8''R-01_diagn%C3%B3sticos.pdf`, "f"))
      .toBe("R-01_diagnósticos.pdf");
    expect(filenameFromDisposition('attachment; filename="R-02.xlsx"', "f")).toBe("R-02.xlsx");
    expect(filenameFromDisposition(null, "respaldo.pdf")).toBe("respaldo.pdf");
  });
});
