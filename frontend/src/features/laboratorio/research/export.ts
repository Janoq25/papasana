/** PNG pHYs (W3C): densidad física, además de píxeles calculados para el ancho impreso. */
export const EXPORT_DPI = 600;
export function exportDimensions(widthCm: number, aspect: number) {
  if (!Number.isFinite(widthCm) || widthCm < 5 || widthCm > 25 || !Number.isFinite(aspect) || aspect <= 0) {
    throw new Error("El ancho de impresión debe estar entre 5 y 25 cm.");
  }
  const width = Math.round(widthCm / 2.54 * EXPORT_DPI);
  const height = Math.round(width / aspect);
  if (width * height > 45_000_000) throw new Error("La figura supera el tamaño de exportación permitido.");
  return { width, height };
}
const encoder = new TextEncoder();
function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
/** Sustituye el pHYs habitual de 96 DPI de canvas; conserva los datos de imagen. */
export function pngWithDpi(png: Uint8Array<ArrayBuffer>, dpi = EXPORT_DPI): Uint8Array<ArrayBuffer> {
  if (png.length < 33 || [137, 80, 78, 71, 13, 10, 26, 10].some((v, i) => png[i] !== v)) {
    throw new Error("El archivo generado no es un PNG válido.");
  }
  const chunk = new Uint8Array(21);
  const view = new DataView(chunk.buffer);
  view.setUint32(0, 9); chunk.set(encoder.encode("pHYs"), 4);
  const ppm = Math.round(dpi / 0.0254);
  view.setUint32(8, ppm); view.setUint32(12, ppm); chunk[16] = 1;
  view.setUint32(17, crc32(chunk.subarray(4, 17)));
  const chunks: Uint8Array<ArrayBuffer>[] = [png.slice(0, 8)];
  const input = new DataView(png.buffer, png.byteOffset, png.byteLength);
  let offset = 8, inserted = false;
  while (offset + 12 <= png.length) {
    const length = input.getUint32(offset);
    const end = offset + length + 12;
    if (end > png.length) throw new Error("PNG truncado.");
    const type = new TextDecoder().decode(png.subarray(offset + 4, offset + 8));
    if (type !== "pHYs") chunks.push(png.slice(offset, end));
    if (type === "IHDR") { chunks.push(chunk); inserted = true; }
    offset = end;
    if (type === "IEND") break;
  }
  if (!inserted) throw new Error("PNG sin cabecera IHDR.");
  const result = new Uint8Array(chunks.reduce((sum, c) => sum + c.length, 0));
  let position = 0;
  chunks.forEach((c) => { result.set(c, position); position += c.length; });
  return result;
}
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename;
  document.body.appendChild(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
export async function exportFigure(svg: SVGSVGElement, widthCm: number, filename: string): Promise<void> {
  const box = svg.viewBox.baseVal;
  const { width, height } = exportDimensions(widthCm, box.width / box.height);
  await document.fonts.ready;
  const copy = svg.cloneNode(true) as SVGSVGElement;
  copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  copy.setAttribute("width", String(width)); copy.setAttribute("height", String(height));
  copy.setAttribute("style", "background:white;font-family:Arial,Helvetica,sans-serif");
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copy)], { type: "image/svg+xml;charset=utf-8" }));
  const canvas = document.createElement("canvas");
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    canvas.width = width; canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Su navegador no permite crear la imagen.");
    context.fillStyle = "#ffffff"; context.fillRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(
      (value) => value ? resolve(value) : reject(new Error("No se pudo crear el PNG.")), "image/png"));
    const bytes = pngWithDpi(new Uint8Array(await blob.arrayBuffer()));
    saveBlob(new Blob([bytes.buffer], { type: "image/png" }), filename);
  } finally { URL.revokeObjectURL(url); canvas.width = 0; canvas.height = 0; }
}
const escape = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
export function tableFormats(title: string, headers: string[], rows: string[][], note: string) {
  const cell = "padding:6pt 9pt;border-bottom:1px solid #c4c4c4;text-align:left;vertical-align:top";
  const html = `<html><body><table style="border-collapse:collapse;font-family:'Times New Roman',serif;font-size:11pt;color:#111;background:white"><caption style="text-align:left;font-weight:bold;padding:8pt 0">${escape(title)}</caption><thead><tr>${headers.map((h) => `<th scope="col" style="${cell};border-top:2px solid #222;border-bottom:2px solid #222;font-weight:bold">${escape(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((v) => `<td style="${cell}">${escape(v)}</td>`).join("")}</tr>`).join("")}</tbody></table><p style="font-family:'Times New Roman',serif;font-size:10pt">${escape(note)}</p></body></html>`;
  return { html, text: [title, headers.join("\t"), ...rows.map((row) => row.join("\t")), note].join("\n") };
}
export async function copyFormattedTable(title: string, headers: string[], rows: string[][], note: string) {
  const { html, text } = tableFormats(title, headers, rows, note);
  if (navigator.clipboard?.write && typeof ClipboardItem !== "undefined") {
    try {
      await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([html], { type: "text/html" }), "text/plain": new Blob([text], { type: "text/plain" }) })]);
      return;
    } catch { /* Intentar el evento copy conservando ambos formatos. */ }
  }
  let wrote = false;
  const handler = (event: ClipboardEvent) => {
    if (!event.clipboardData) return;
    event.clipboardData.setData("text/html", html); event.clipboardData.setData("text/plain", text);
    event.preventDefault(); wrote = true;
  };
  document.addEventListener("copy", handler);
  try { document.execCommand("copy"); } catch { /* Error visible a continuación. */ }
  finally { document.removeEventListener("copy", handler); }
  if (!wrote) throw new Error("El navegador bloqueó el portapapeles. Permita copiar en este sitio y vuelva a intentarlo.");
}
