import type { PolygonGeometry } from "../api/types";

/** Vértice en orden Leaflet: [lat, lon]. GeoJSON usa [lon, lat]. */
export type LatLng = [number, number];

export const DEFAULT_CENTER: LatLng = [-12.05, -75.25]; // valle del Mantaro (Junín)

/** Convierte vértices [lat, lon] en un polígono GeoJSON cerrado. Devuelve null si hay menos de 3 vértices. */
export function toPolygon(vertices: LatLng[]): PolygonGeometry | null {
  if (vertices.length < 3) return null;
  const ring = vertices.map(([lat, lon]) => [round6(lon), round6(lat)]);
  ring.push([...ring[0]]);
  return { type: "Polygon", coordinates: [ring] };
}

/** Vértices [lat, lon] de un polígono GeoJSON (sin repetir el vértice de cierre). */
export function fromPolygon(geometry: PolygonGeometry | null | undefined): LatLng[] {
  if (!geometry?.coordinates?.[0]) return [];
  const ring = geometry.coordinates[0].map(([lon, lat]) => [lat, lon] as LatLng);
  const [first, last] = [ring[0], ring[ring.length - 1]];
  if (ring.length > 1 && first[0] === last[0] && first[1] === last[1]) ring.pop();
  return ring;
}

/** Área aproximada en hectáreas (fórmula del área esférica). El valor oficial lo calcula PostGIS. */
export function approxAreaHa(vertices: LatLng[]): number {
  if (vertices.length < 3) return 0;
  const R = 6378137;
  const rad = (d: number) => (d * Math.PI) / 180;
  let sum = 0;
  for (let i = 0; i < vertices.length; i++) {
    const [lat1, lon1] = vertices[i];
    const [lat2, lon2] = vertices[(i + 1) % vertices.length];
    sum += rad(lon2 - lon1) * (2 + Math.sin(rad(lat1)) + Math.sin(rad(lat2)));
  }
  return Math.abs((sum * R * R) / 2) / 10_000;
}

/** ¿Algún par de lados no adyacentes se cruza? (polígono no válido). */
export function selfIntersects(vertices: LatLng[]): boolean {
  const n = vertices.length;
  if (n < 4) return false;
  const cross = (a: LatLng, b: LatLng, c: LatLng) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const intersects = (p1: LatLng, p2: LatLng, p3: LatLng, p4: LatLng) =>
    cross(p3, p4, p1) * cross(p3, p4, p2) < 0 && cross(p1, p2, p3) * cross(p1, p2, p4) < 0;
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (Math.abs(i - j) <= 1 || (i === 0 && j === n - 1)) continue;
      if (intersects(vertices[i], vertices[(i + 1) % n], vertices[j], vertices[(j + 1) % n])) return true;
    }
  }
  return false;
}

function round6(v: number): number {
  return Math.round(v * 1e6) / 1e6;
}
