import { useEffect } from "react";
import { Box, Typography } from "@mui/material";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { DEFAULT_CENTER } from "../utils/geo";
import { OSM_ATTRIBUTION, OSM_URL } from "./maps";

export interface HeatPoint {
  lat: number;
  lon: number;
  peso: number;
}

const GRADIENT = { 0.3: "#2e6b30", 0.55: "#f2c200", 0.8: "#e07000", 1: "#b3261e" };

type HeatFactory = (latlngs: [number, number, number][], options: Record<string, unknown>) => L.Layer;

/** leaflet.heat 0.2 es un script que se registra sobre el `L` global: se carga una sola vez, bajo demanda. */
let heatLoader: Promise<HeatFactory> | null = null;
function loadHeat(): Promise<HeatFactory> {
  if (!heatLoader) {
    (window as unknown as { L: typeof L }).L = L;
    heatLoader = import("leaflet.heat/dist/leaflet-heat.js").then(
      () => (L as unknown as { heatLayer: HeatFactory }).heatLayer,
    );
  }
  return heatLoader;
}

function HeatLayer({ points }: { points: HeatPoint[] }) {
  const map = useMap();
  useEffect(() => {
    let layer: L.Layer | null = null;
    let cancelled = false;
    void loadHeat().then((heatLayer) => {
      if (cancelled) return;
      layer = heatLayer(points.map((p) => [p.lat, p.lon, p.peso]), {
        radius: 28, blur: 20, maxZoom: 14, minOpacity: 0.35, gradient: GRADIENT,
      });
      layer.addTo(map);
    });
    if (points.length) {
      const bounds = L.latLngBounds(points.map((p) => [p.lat, p.lon] as [number, number]));
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
    }
    return () => {
      cancelled = true;
      if (layer) map.removeLayer(layer);
    };
  }, [map, points]);
  return null;
}

/** Mapa de calor de casos (PostGIS + Leaflet). El peso refleja la categoría del diagnóstico. */
export default function HeatMap({ points, height = 380 }: { points: HeatPoint[]; height?: number }) {
  return (
    <Box>
      <Box sx={{ height, borderRadius: 1, overflow: "hidden", border: 1, borderColor: "divider" }}
        role="img" aria-label={`Mapa de calor con ${points.length} casos georreferenciados`}>
        <MapContainer center={DEFAULT_CENTER} zoom={9} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
          <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_URL} />
          <HeatLayer points={points} />
        </MapContainer>
      </Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1 }} aria-hidden="true">
        <Typography variant="caption" color="text.secondary">Menor</Typography>
        <Box sx={{ width: 160, height: 10, borderRadius: 5,
          background: "linear-gradient(90deg, #2e6b30, #f2c200, #e07000, #b3261e)" }} />
        <Typography variant="caption" color="text.secondary">Mayor concentración de casos compatibles</Typography>
      </Box>
    </Box>
  );
}
