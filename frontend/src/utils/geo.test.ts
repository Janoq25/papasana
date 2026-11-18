import { describe, expect, it } from "vitest";
import { approxAreaHa, fromPolygon, selfIntersects, toPolygon, type LatLng } from "./geo";

const square: LatLng[] = [
  [-12.05, -75.25],
  [-12.05, -75.249],
  [-12.049, -75.249],
  [-12.049, -75.25],
];

describe("utilidades de geometría", () => {
  it("convierte [lat, lon] a GeoJSON [lon, lat] y cierra el anillo", () => {
    const poly = toPolygon(square)!;
    expect(poly.coordinates[0][0]).toEqual([-75.25, -12.05]);
    expect(poly.coordinates[0]).toHaveLength(5);
    expect(poly.coordinates[0][4]).toEqual(poly.coordinates[0][0]);
    expect(fromPolygon(poly)).toEqual(square);
  });

  it("requiere al menos 3 vértices", () => {
    expect(toPolygon(square.slice(0, 2))).toBeNull();
  });

  it("calcula un área aproximada coherente (~1,2 ha para 0,001° × 0,001° a 12° S)", () => {
    const ha = approxAreaHa(square);
    expect(ha).toBeGreaterThan(1.1);
    expect(ha).toBeLessThan(1.3);
  });

  it("detecta polígonos que se cruzan (forma de moño)", () => {
    const bowtie: LatLng[] = [square[0], square[2], square[1], square[3]];
    expect(selfIntersects(bowtie)).toBe(true);
    expect(selfIntersects(square)).toBe(false);
  });
});
