import type { ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";
import { Box, Card, CardContent, Grid, Link, Tooltip, Typography } from "@mui/material";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import type { DashboardData } from "../../api/types";
import { percent } from "../../utils/diagnosis";

type Accent = "primary" | "success" | "warning" | "error" | "grey";

export function KpiCard({ title, value, subtitle, accent = "primary", info, children }: {
  title: string;
  value: ReactNode;
  subtitle?: ReactNode;
  accent?: Accent;
  info?: string;
  children?: ReactNode;
}) {
  const color = accent === "grey" ? "grey.500" : `${accent}.main`;
  return (
    <Card variant="outlined" sx={{ height: "100%", borderLeft: 4, borderLeftColor: color }}>
      <CardContent>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Typography variant="body2" color="text.secondary" component="h3">{title}</Typography>
          {info && (
            <Tooltip title={info}>
              <InfoOutlinedIcon fontSize="inherit" color="action" aria-label={info} tabIndex={0} />
            </Tooltip>
          )}
        </Box>
        <Typography variant="h4" component="p" sx={{ fontWeight: 600, my: 0.5 }}>{value}</Typography>
        {subtitle && <Typography variant="caption" color="text.secondary" component="div">{subtitle}</Typography>}
        {children}
      </CardContent>
    </Card>
  );
}

const fmt = (n: number) => n.toLocaleString("es-PE");

export default function KpiGrid({ kpis, canValidate }: { kpis: DashboardData["kpis"]; canValidate: boolean }) {
  const cat = Object.fromEntries(kpis.por_categoria.map((c) => [c.categoria, c]));
  const share = (k: "sano" | "sospechoso" | "tizon_tardio_compatible") =>
    cat[k]?.porcentaje == null ? "—" : percent(cat[k].porcentaje!);
  const recent = kpis.parcelas_con_casos_compatibles;
  const agreement = kpis.acuerdo_experto;
  const cards: ReactNode[] = [
    <KpiCard key="total" title="Diagnósticos realizados" value={fmt(kpis.diagnosticos)} subtitle="En el periodo y filtros elegidos" />,
    <KpiCard key="tizon" title="Tizón tardío: síntomas compatibles" accent="error"
      value={fmt(cat.tizon_tardio_compatible?.total ?? 0)} subtitle={`${share("tizon_tardio_compatible")} del total`} />,
    <KpiCard key="sosp" title="Sospechosos" accent="warning" value={fmt(cat.sospechoso?.total ?? 0)}
      subtitle={`${share("sospechoso")} del total`} />,
    <KpiCard key="sano" title="Sanos" accent="success" value={fmt(cat.sano?.total ?? 0)} subtitle={`${share("sano")} del total`} />,
    <KpiCard key="pend" title="Pendientes de validación experta" accent="warning" value={fmt(kpis.pendientes_validacion)}
      subtitle={canValidate ? <Link component={RouterLink} to="/validacion">Ir a la bandeja de validación</Link>
        : "Casos que esperan revisión del especialista"} />,
    <KpiCard key="parc" title="Parcelas con casos compatibles" accent="error"
      value={`${fmt(recent.valor)} de ${fmt(kpis.parcelas)}`}
      subtitle={`Últimos ${recent.dias} días (hasta el ${recent.hasta.split("-").reverse().join("/")})`} />,
    <KpiCard key="acuerdo" title="Acuerdo con la validación experta" accent="primary"
      value={agreement.valor == null ? "—" : percent(agreement.valor)}
      subtitle={agreement.n ? `${agreement.confirma} confirmados y ${agreement.corrige} corregidos` : "Aún no hay casos revisados"}
      info="Casos en que el especialista confirmó la predicción, sobre los confirmados o corregidos. No es una métrica de evaluación del modelo: los casos revisados no son una muestra aleatoria." />,
    <KpiCard key="precision" title="Precisión del modelo en producción" accent="grey"
      value={kpis.precision_modelo.valor == null ? "—" : percent(kpis.precision_modelo.valor)}
      subtitle={kpis.precision_modelo.motivo ?? "Según las métricas registradas del modelo en producción"} />,
    <KpiCard key="alertas" title="Alertas activas" accent="grey" value="—" subtitle={kpis.alertas_activas.motivo} />,
    <KpiCard key="riesgo" title="Parcelas en riesgo climático" accent="grey" value="—" subtitle={kpis.parcelas_en_riesgo.motivo} />,
  ];
  return (
    <Grid container spacing={2}>
      {cards.map((c, i) => (
        <Grid key={i} size={{ xs: 12, sm: 6, md: 4, lg: i < 4 ? 3 : 4 }}>{c}</Grid>
      ))}
    </Grid>
  );
}
