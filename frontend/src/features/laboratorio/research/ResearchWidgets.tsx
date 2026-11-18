import { useRef, useState, type ReactNode } from "react";
import { Alert, Box, Button, Chip, Dialog, DialogContent, DialogTitle, DialogActions, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TableSortLabel, Typography } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { copyFormattedTable, exportFigure } from "./export";
import { number } from "./types";
export function Figure({ title, caption, filename, widthCm, children }: {
  title: string; caption: string; filename: string; widthCm: number; children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(""), [error, setError] = useState("");
  async function download() {
    setBusy(true); setError(""); setMessage("");
    try {
      const svg = ref.current?.querySelector("svg");
      if (!svg) throw new Error("La figura todavía no está disponible.");
      await exportFigure(svg, widthCm, `${filename}-600dpi.png`);
      setMessage("Imagen exportada a 600 DPI.");
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo exportar la figura."); }
    finally { setBusy(false); }
  }
  return <Paper variant="outlined" component="figure" sx={{ m: 0, p: { xs: 1.5, md: 2.5 }, minWidth: 0 }}>
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", mb: 2 }}>
      <Typography variant="h3" component="h3" sx={{ flex: "1 1 240px" }}>{title}</Typography>
      <Button size="small" onClick={() => setExpanded(true)} aria-label={`Ampliar ${title}`}>Ampliar</Button>
      <Button size="small" variant="outlined" startIcon={<DownloadIcon />} aria-label={`Exportar ${title} a 600 DPI`} onClick={() => void download()} disabled={busy}>
        {busy ? "Exportando…" : "PNG · 600 DPI"}
      </Button>
    </Box>
    <Box ref={ref} sx={{ bgcolor: "#fff", overflow: "hidden", "& svg": { display: "block", width: "100%", height: "auto" } }}>{children}</Box>
    <Typography component="figcaption" variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>{caption}</Typography>
    <Dialog open={expanded} onClose={() => setExpanded(false)} fullWidth maxWidth="lg" aria-label={title}>
      <DialogTitle>{title}</DialogTitle><DialogContent><Box sx={{ "& svg": { width: "100%", height: "auto" } }}>{children}</Box><Typography variant="body2">{caption}</Typography></DialogContent>
      <DialogActions><Button onClick={() => setExpanded(false)}>Cerrar</Button><Button disabled={busy} onClick={() => void download()}>Exportar PNG a 600 DPI</Button></DialogActions>
    </Dialog>
    {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
    <Box role="status" aria-live="polite">{message && <Chip size="small" color="success" variant="outlined" label={message} sx={{ mt: 1 }} />}</Box>
  </Paper>;
}
type Cell = string | number | null | undefined;
const display = (value: Cell, digits?: number) => typeof value === "number" ? number(value, digits ?? (Number.isInteger(value) ? 0 : 4)) : value ?? "—";
export function ResearchTable({ title, headers, rows, note, decimals }: { title: string; headers: string[]; rows: Cell[][]; note: string; decimals?: Record<number, number> }) {
  const [sort, setSort] = useState<{ col: number; asc: boolean } | null>(null);
  const [message, setMessage] = useState(""), [error, setError] = useState("");
  const ordered = sort ? [...rows].sort((a, b) => {
    const x = a[sort.col], y = b[sort.col];
    const result = typeof x === "number" && typeof y === "number" ? x - y : display(x).localeCompare(display(y), "es", { numeric: true });
    return sort.asc ? result : -result;
  }) : rows;
  async function copy() {
    setMessage(""); setError("");
    try { await copyFormattedTable(title, headers, ordered.map((row) => row.map((value, col) => display(value, decimals?.[col]))), note); setMessage("Tabla copiada con formato. Péguela conservando el formato de origen."); }
    catch (e) { setError(e instanceof Error ? e.message : "No se pudo copiar la tabla."); }
  }
  return <Paper variant="outlined" sx={{ p: { xs: 1.5, md: 2.5 }, minWidth: 0 }}>
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", mb: 1 }}>
      <Typography variant="h3" component="h3" sx={{ flex: "1 1 240px" }}>{title}</Typography>
      <Button size="small" variant="outlined" startIcon={<ContentCopyIcon />} onClick={() => void copy()} aria-label={`Copiar ${title} con formato`}>Copiar con formato</Button>
    </Box>
    <TableContainer tabIndex={0} role="region" aria-label={title} sx={{ "&:focus-visible": { outline: "2px solid", outlineColor: "primary.main" } }}>
      <Table size="small" aria-label={title}>
        <TableHead><TableRow>{headers.map((h, col) => <TableCell key={h} sortDirection={sort?.col === col ? (sort.asc ? "asc" : "desc") : false}>
          <TableSortLabel active={sort?.col === col} direction={sort?.col === col && !sort.asc ? "desc" : "asc"} onClick={() => setSort({ col, asc: sort?.col === col ? !sort.asc : true })}>{h}</TableSortLabel>
        </TableCell>)}</TableRow></TableHead>
        <TableBody>{ordered.map((row, i) => <TableRow key={i}>{row.map((value, col) => <TableCell key={col} component={col === 0 ? "th" : "td"} scope={col === 0 ? "row" : undefined} sx={{ fontVariantNumeric: "tabular-nums", overflowWrap: "anywhere", minWidth: col === 0 ? 150 : 80 }}>{display(value, decimals?.[col])}</TableCell>)}</TableRow>)}</TableBody>
      </Table>
    </TableContainer>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>{note}</Typography>
    {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
    <Typography role="status" aria-live="polite" variant="body2" color="success.main" sx={{ mt: message ? 1 : 0 }}>{message}</Typography>
  </Paper>;
}
