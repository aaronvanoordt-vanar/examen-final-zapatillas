import { read, utils } from 'xlsx';
import type { Producto } from './bm25';

const REPO = 'aaronvanoordt-vanar/examen-final-zapatillas';
const RAMA = 'datos';
const ARCHIVO = 'zapatillas.xlsx';

// La API de GitHub no cachea el archivo (cada ejecucion de n8n se ve al instante);
// raw.githubusercontent.com queda como respaldo si se agota el limite de la API.
export const FUENTES: { url: string; headers: Record<string, string> }[] = [
  {
    url: `https://api.github.com/repos/${REPO}/contents/${ARCHIVO}?ref=${RAMA}`,
    headers: { Accept: 'application/vnd.github.raw' },
  },
  { url: `https://raw.githubusercontent.com/${REPO}/${RAMA}/${ARCHIVO}`, headers: {} },
];

type Fila = Record<string, unknown>;

function texto(v: unknown): string {
  return String(v ?? '').replace(/\s+/g, ' ').trim();
}

function numero(v: unknown): number {
  if (typeof v === 'number') return v;
  const n = parseFloat(texto(v).replace(/[^\d.,-]/g, '').replace(/,/g, ''));
  return Number.isFinite(n) ? n : NaN;
}

/** Convierte las filas del Excel (columnas Tienda, Marca, Modelo, Precio, Moneda, URL, Fecha de scrapeo). */
export function filasAProductos(filas: Fila[]): Producto[] {
  return filas
    .map((f) => ({
      tienda: texto(f['Tienda']),
      marca: texto(f['Marca']),
      modelo: texto(f['Modelo']),
      precio: numero(f['Precio']),
      moneda: texto(f['Moneda']) || 'PEN',
      url: texto(f['URL']),
      fecha: texto(f['Fecha de scrapeo']),
    }))
    .filter((p) => p.tienda && p.modelo && Number.isFinite(p.precio));
}

export function leerExcel(buffer: ArrayBuffer): Producto[] {
  const libro = read(buffer, { type: 'array' });
  const hoja = libro.Sheets[libro.SheetNames[0]];
  return filasAProductos(utils.sheet_to_json<Fila>(hoja, { defval: '' }));
}

export function ultimaFecha(productos: Producto[]): string {
  return productos.reduce((max, p) => (p.fecha > max ? p.fecha : max), '');
}

export async function cargarProductos(): Promise<Producto[]> {
  let ultimoError: unknown;
  // Solo para desarrollo local: VITE_XLSX_URL apunta a un Excel servido localmente.
  const local = import.meta.env.DEV ? import.meta.env.VITE_XLSX_URL : undefined;
  const fuentes = local ? [{ url: local, headers: {} }, ...FUENTES] : FUENTES;
  for (const fuente of fuentes) {
    try {
      const resp = await fetch(fuente.url, { headers: fuente.headers, cache: 'no-store' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status} en ${fuente.url}`);
      return leerExcel(await resp.arrayBuffer());
    } catch (e) {
      ultimoError = e;
    }
  }
  throw ultimoError;
}
