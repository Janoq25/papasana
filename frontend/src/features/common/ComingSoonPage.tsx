import { Alert, Box, Typography } from "@mui/material";
import PageHeader from "../../components/PageHeader";

const DESCRIPTIONS: Record<string, string> = {
  dashboard: "KPIs, tendencias, distribución por región y variedad y mapa de calor de casos.",
  parcelas: "Parcelas georreferenciadas con productor, variedad, fecha de siembra y estadio fenológico.",
  diagnostico: "Carga de fotografías de hojas, clasificación por síntomas, confianza y mapa Grad-CAM.",
  validacion: "Bandeja de casos que requieren revisión: el especialista confirma o corrige la etiqueta.",
  alertas: "Índice de riesgo de Phytophthora infestans (criterios Hutton/Smith) y alertas combinadas.",
  asistente: "Asistente RAG que explica diagnósticos citando documento y página.",
  reportes: "Reportes operacionales y de gestión en PDF, Word y Excel.",
  laboratorio: "Comparación de los 5 modelos, métricas, pruebas estadísticas y promoción de versiones.",
  datasets: "Registro de datasets con licencia, cita y tipo de etiqueta.",
  base_documental: "Documentos técnicos de FAO, SENASA e INIA indexados para el asistente.",
  catalogos: "Variedades de papa, estadios fenológicos, ubigeo y enfermedades diferenciales.",
};

export default function ComingSoonPage({ title, module, phase }: { title: string; module: string; phase: number }) {
  return (
    <Box>
      <PageHeader title={title} />
      <Alert severity="info" sx={{ maxWidth: 720 }}>
        <Typography variant="body1" sx={{ fontWeight: 600 }}>
          Este módulo se implementa en la Fase {phase}.
        </Typography>
        <Typography variant="body2">{DESCRIPTIONS[module]}</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          Su acceso ya está controlado por permisos y la entrada y salida quedan registradas en la bitácora.
        </Typography>
      </Alert>
    </Box>
  );
}
