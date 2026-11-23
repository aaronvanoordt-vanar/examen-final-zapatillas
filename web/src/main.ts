import './style.css';
import { IndiceBM25, type Producto, type Resultado } from './bm25';
import { cargarProductos, ultimaFecha } from './datos';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const input = $<HTMLInputElement>('q');
const cuerpo = $<HTMLTableSectionElement>('resultados');
const estado = $<HTMLParagraphElement>('estado');
const filtros = $<HTMLDivElement>('filtros');

let productos: Producto[] = [];
let indice = new IndiceBM25([]);
let tiendaActiva = '';

const soles = new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' });

function escapar(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

function fila(r: Resultado, i: number, minimo: number): string {
  const p = r.producto;
  const barato = p.precio === minimo ? '<span class="barato">más barato</span>' : '';
  const puntaje = r.puntaje > 0 ? r.puntaje.toFixed(3) : '—';
  return `<tr>
    <td class="num">${i + 1}</td>
    <td class="num puntaje">${puntaje}</td>
    <td><span class="tienda t-${escapar(p.tienda.toLowerCase())}">${escapar(p.tienda)}</span></td>
    <td>${escapar(p.marca)}</td>
    <td>${escapar(p.modelo)}</td>
    <td class="num precio">${soles.format(p.precio)} ${barato}</td>
    <td><a href="${escapar(p.url)}" target="_blank" rel="noopener">Ver producto</a></td>
  </tr>`;
}

function render(): void {
  const consulta = input.value.trim();
  let lista: Resultado[] = consulta
    ? indice.buscar(consulta)
    : [...productos].sort((a, b) => a.precio - b.precio).map((producto) => ({ producto, puntaje: 0 }));
  if (tiendaActiva) lista = lista.filter((r) => r.producto.tienda === tiendaActiva);

  const minimo = Math.min(...lista.map((r) => r.producto.precio));
  cuerpo.innerHTML = lista.map((r, i) => fila(r, i, minimo)).join('');
  estado.textContent = consulta
    ? `${lista.length} resultado(s) para "${consulta}", ordenados por puntaje BM25.`
    : `Catálogo completo: ${lista.length} zapatillas, ordenadas por precio.`;

  const url = new URL(location.href);
  if (consulta) url.searchParams.set('q', consulta);
  else url.searchParams.delete('q');
  history.replaceState(null, '', url);
}

function renderFiltros(): void {
  const tiendas = [...new Set(productos.map((p) => p.tienda))].sort();
  const boton = (t: string, etiqueta: string) =>
    `<button type="button" data-tienda="${escapar(t)}" class="${t === tiendaActiva ? 'activo' : ''}">${escapar(etiqueta)}</button>`;
  filtros.innerHTML =
    boton('', `Todas (${productos.length})`) +
    tiendas.map((t) => boton(t, `${t} (${productos.filter((p) => p.tienda === t).length})`)).join('');
}

$<HTMLFormElement>('form').addEventListener('submit', (e) => {
  e.preventDefault();
  render();
});
let espera: number | undefined;
input.addEventListener('input', () => {
  clearTimeout(espera);
  espera = window.setTimeout(render, 150);
});
document.querySelector('.sugerencias')?.addEventListener('click', (e) => {
  const q = (e.target as HTMLElement).dataset.q;
  if (q) {
    input.value = q;
    render();
  }
});
filtros.addEventListener('click', (e) => {
  const t = (e.target as HTMLElement).dataset.tienda;
  if (t !== undefined) {
    tiendaActiva = t;
    renderFiltros();
    render();
  }
});

async function iniciar(): Promise<void> {
  estado.textContent = 'Cargando zapatillas.xlsx...';
  try {
    productos = await cargarProductos();
    indice = new IndiceBM25(productos);
    $('fecha').textContent = ultimaFecha(productos) || 'sin datos aún';
    $('conteo').textContent = `${productos.length} zapatillas · ${new Set(productos.map((p) => p.tienda)).size} tiendas`;
    input.value = new URL(location.href).searchParams.get('q') ?? '';
    renderFiltros();
    render();
    if (!productos.length) estado.textContent = 'El Excel aún no tiene productos. Ejecuta el workflow de n8n.';
  } catch (e) {
    $('fecha').textContent = 'error';
    estado.textContent = `No se pudo leer zapatillas.xlsx: ${(e as Error).message}`;
  }
}

iniciar();
