import { afterEach, describe, expect, it, vi } from "vitest";
import { copyFormattedTable, exportDimensions, pngWithDpi, tableFormats } from "./export";
const sample = () => Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII="), (c) => c.charCodeAt(0));
function chunks(bytes: Uint8Array) {
  const out: { type: string; data: Uint8Array }[] = [];
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  for (let pos = 8; pos < bytes.length;) {
    const length = view.getUint32(pos);
    out.push({ type: new TextDecoder().decode(bytes.slice(pos + 4, pos + 8)), data: bytes.slice(pos + 8, pos + 8 + length) });
    pos += length + 12;
  }
  return out;
}
afterEach(() => vi.unstubAllGlobals());
describe("exportación para publicación", () => {
  it("calcula píxeles desde centímetros a 600 DPI", () => {
    expect(exportDimensions(17.5, 2)).toEqual({ width: 4134, height: 2067 });
    expect(exportDimensions(8.5, 1).width).toBe(2008);
    expect(() => exportDimensions(100, 1)).toThrow();
  });
  it("inserta una única densidad física 600 DPI sin alterar los datos de imagen", () => {
    const original = sample();
    const output = pngWithDpi(pngWithDpi(original, 96));
    const all = chunks(output), density = all.filter((c) => c.type === "pHYs");
    expect(density).toHaveLength(1);
    const view = new DataView(density[0].data.buffer);
    expect(view.getUint32(0)).toBe(23622); expect(view.getUint32(4)).toBe(23622); expect(view.getUint8(8)).toBe(1);
    expect(all.find((c) => c.type === "IDAT")!.data).toEqual(chunks(original).find((c) => c.type === "IDAT")!.data);
    expect(() => pngWithDpi(new Uint8Array([1, 2]))).toThrow("PNG válido");
  });
  it("genera tabla HTML editable, texto alternativo y escapa contenido", () => {
    const { html, text } = tableFormats("Resultados <piloto>", ["Modelo", "F1"], [["<img src=x onerror=alert(1)>", "0,9931"]], "Fuente & notas");
    expect(html).toContain("<table"); expect(html).toContain("<thead>"); expect(html).toContain("Times New Roman");
    expect(html).toContain("&lt;img"); expect(html).not.toContain("<img"); expect(html).toContain("Fuente &amp; notas");
    expect(text).toContain("Modelo\tF1"); expect(text).toContain("0,9931");
  });
  it("copia HTML y texto en el mismo elemento del portapapeles", async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { write } });
    vi.stubGlobal("ClipboardItem", class { constructor(public values: Record<string, Blob>) {} });
    await copyFormattedTable("Tabla", ["Modelo"], [["ResNet50"]], "Fuente");
    expect(write).toHaveBeenCalledOnce();
    expect(Object.keys(write.mock.calls[0][0][0].values)).toEqual(["text/html", "text/plain"]);
  });
  it("no anuncia éxito si el navegador bloquea la copia", async () => {
    vi.stubGlobal("navigator", {}); vi.stubGlobal("ClipboardItem", undefined);
    await expect(copyFormattedTable("Tabla", ["A"], [["B"]], "Fuente")).rejects.toThrow("bloqueó");
  });
});
