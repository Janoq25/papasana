import { useEffect, useMemo } from "react";
import { Box, Button, Stack, Typography } from "@mui/material";
import { CircleMarker, GeoJSON, MapContainer, Polygon, Polyline, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { ParcelFeatureCollection } from "../api/types";
import { approxAreaHa, DEFAULT_CENTER, selfIntersects, type LatLng } from "../utils/geo";

export const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">colaboradores de OpenStreetMap</a>';
export const OSM_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

function FitBounds({ bounds }: { bounds: L.LatLngBounds | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.isValid()) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 17 });
  }, [map, bounds]);
  return null;
}

/** Mapa de parcelas (polígonos GeoJSON). */
export function ParcelsMap({
  data,
  selectedId,
  onSelect,
  height = 420,
}: {
  data: ParcelFeatureCollection | undefined;
  selectedId?: number | null;
  onSelect?: (id: number) => void;
  height?: number;
}) {
  const bounds = useMemo(() => {
    if (!data?.features.length) return null;
    return L.geoJSON(data as unknown as GeoJSON.FeatureCollection).getBounds();
  }, [data]);
  return (
    <Box sx={{ height, borderRadius: 2, overflow: "hidden", border: 1, borderColor: "divider" }}
      role="region" aria-label="Mapa de parcelas">
      <MapContainer center={DEFAULT_CENTER} zoom={12} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
        <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_URL} />
        {data && (
          <GeoJSON
            key={`${data.features.length}-${selectedId ?? ""}`}
            data={data as unknown as GeoJSON.FeatureCollection}
            style={(f) => ({
              color: f?.properties?.id === selectedId ? "#7a4b12" : "#2e5e1f",
              weight: f?.properties?.id === selectedId ? 4 : 2,
              fillOpacity: 0.25,
            })}
            onEachFeature={(f, layer) => {
              const p = f.properties as { id: number; code: string; name: string; area_ha: number };
              layer.bindTooltip(`${p.code} · ${p.name} (${p.area_ha.toFixed(2)} ha)`);
              layer.on("click", () => onSelect?.(p.id));
            }}
          />
        )}
        <FitBounds bounds={bounds} />
      </MapContainer>
    </Box>
  );
}

function ClickToAdd({ onAdd }: { onAdd: (v: LatLng) => void }) {
  useMapEvents({ click: (e) => onAdd([e.latlng.lat, e.latlng.lng]) });
  return null;
}

/** Editor de polígono: cada clic agrega un vértice; el polígono se cierra automáticamente. */
export function PolygonEditor({
  vertices,
  onChange,
  context,
  height = 360,
}: {
  vertices: LatLng[];
  onChange: (v: LatLng[]) => void;
  context?: ParcelFeatureCollection;
  height?: number;
}) {
  const initialBounds = useMemo(() => {
    if (vertices.length >= 3) return L.latLngBounds(vertices);
    if (context?.features.length) return L.geoJSON(context as unknown as GeoJSON.FeatureCollection).getBounds();
    return null;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const invalid = selfIntersects(vertices);
  return (
    <Box>
      <Box sx={{ height, borderRadius: 2, overflow: "hidden", border: 1, borderColor: invalid ? "error.main" : "divider", cursor: "crosshair" }}
        role="application" aria-label="Editor del polígono de la parcela: haga clic en el mapa para agregar vértices">
        <MapContainer center={DEFAULT_CENTER} zoom={13} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
          <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_URL} />
          {context && (
            <GeoJSON data={context as unknown as GeoJSON.FeatureCollection}
              style={{ color: "#888", weight: 1, fillOpacity: 0.08, dashArray: "4" }} interactive={false} />
          )}
          {vertices.length >= 3 ? (
            <Polygon positions={vertices} pathOptions={{ color: invalid ? "#b3261e" : "#7a4b12", weight: 3, fillOpacity: 0.3 }} />
          ) : (
            vertices.length === 2 && <Polyline positions={vertices} pathOptions={{ color: "#7a4b12", weight: 3 }} />
          )}
          {vertices.map((v, i) => (
            <CircleMarker key={i} center={v} radius={5} pathOptions={{ color: "#7a4b12", fillColor: "#fff", fillOpacity: 1 }} />
          ))}
          <ClickToAdd onAdd={(v) => onChange([...vertices, v])} />
          <FitBounds bounds={initialBounds} />
        </MapContainer>
      </Box>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1, alignItems: { sm: "center" } }}>
        <Typography variant="body2" sx={{ flexGrow: 1 }} color={invalid ? "error" : "text.secondary"} aria-live="polite">
          {vertices.length < 3
            ? `Haga clic en el mapa para marcar los vértices (${vertices.length}/3 mínimo).`
            : invalid
              ? "Los lados del polígono se cruzan: deshaga el último vértice."
              : `${vertices.length} vértices · ≈ ${approxAreaHa(vertices).toFixed(2)} ha (el área oficial la calcula PostGIS)`}
        </Typography>
        <Button size="small" onClick={() => onChange(vertices.slice(0, -1))} disabled={!vertices.length}>Deshacer</Button>
        <Button size="small" color="error" onClick={() => onChange([])} disabled={!vertices.length}>Limpiar</Button>
      </Stack>
    </Box>
  );
}
