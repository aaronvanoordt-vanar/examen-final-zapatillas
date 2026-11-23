import { describe, expect, it } from 'vitest';
import { utils, write } from 'xlsx';
import { IndiceBM25, normalizar, type Producto } from '../src/bm25';
import { leerExcel, ultimaFecha } from '../src/datos';

const p = (id: string, tienda: string, marca: string, modelo: string, precio: number): Producto => ({
  tienda,
  marca,
  modelo: `${modelo} [${id}]`,
  precio,
  moneda: 'PEN',
  url: `https://example.pe/${id}`,
  fecha: '2026-11-23 12:00',
});

const catalogo: Producto[] = [
  p('d1', 'Oechsle', 'NIKE', 'Zapatillas Running Nike Hombre Pegasus 41', 499),
  p('d2', 'Footloose', 'NIKE', 'Zapatillas Urbanas Nike Mujer Court', 299),
  p('d3', 'Estilos', 'ADIDAS', 'Zapatillas Running Adidas Hombre Duramo', 259),
  p('d4', 'Oechsle', 'PUMA', 'Zapatillas Urbanas Puma Hombre Atlético Rebound', 199),
  p('d5', 'Footloose', 'NIKE', 'Zapatillas Running Nike Hombre Pegasus 41', 479),
];

const ids = (consulta: string) =>
  new IndiceBM25(catalogo).buscar(consulta).map((r) => r.producto.url.split('/').pop());

describe('BM25: orden de resultados', () => {
  it('"nike running hombre": primero los que tienen las tres palabras, luego los parciales', () => {
    // CASO 7: orden roto a proposito (el correcto es d5, d1, d3, d2, d4)
    expect(ids('nike running hombre')).toEqual(['d4', 'd2', 'd3', 'd1', 'd5']);
  });

  it('mismo modelo en dos tiendas empata en puntaje y sale primero el mas barato', () => {
    const r = new IndiceBM25(catalogo).buscar('pegasus');
    expect(r.map((x) => x.producto.tienda)).toEqual(['Footloose', 'Oechsle']);
    expect(r[0].puntaje).toBeCloseTo(r[1].puntaje, 10);
    expect(r[0].producto.precio).toBeLessThan(r[1].producto.precio);
  });

  it('los puntajes vienen ordenados de mayor a menor y son positivos', () => {
    const r = new IndiceBM25(catalogo).buscar('zapatillas nike urbanas');
    expect(r.length).toBeGreaterThan(0);
    for (let i = 1; i < r.length; i++) expect(r[i - 1].puntaje).toBeGreaterThanOrEqual(r[i].puntaje);
    expect(r[0].producto.url).toMatch(/d2$/);
  });

  it('un termino raro pesa mas que uno comun (IDF)', () => {
    const indice = new IndiceBM25(catalogo);
    expect(indice.idf('rebound')).toBeGreaterThan(indice.idf('zapatillas'));
  });

  it('consulta sin coincidencias devuelve lista vacia', () => {
    expect(ids('botas de lluvia')).toEqual([]);
  });
});

describe('Busqueda insensible a mayusculas y tildes', () => {
  it('normaliza texto', () => {
    expect(normalizar('ZAPATILLAS ATLÉTICO Ñandú')).toBe('zapatillas atletico nandu');
  });

  it('"ZAPATILLAS ATLÉTICO" y "zapatillas atletico" devuelven lo mismo en el mismo orden', () => {
    const a = ids('ZAPATILLAS ATLÉTICO');
    expect(a).toEqual(ids('zapatillas atletico'));
    expect(a[0]).toBe('d4');
  });

  it('"ZAPATILLAS NIKE" y "zapatillas nike" devuelven lo mismo', () => {
    expect(ids('ZAPATILLAS NIKE')).toEqual(ids('zapatillas nike'));
  });
});

describe('Lectura del Excel generado por n8n', () => {
  it('lee las columnas pedidas y calcula la ultima fecha de scrapeo', () => {
    const hoja = utils.json_to_sheet([
      { Tienda: 'Oechsle', Marca: 'NIKE', Modelo: 'Pegasus', Precio: 499.9, Moneda: 'PEN', URL: 'https://a', 'Fecha de scrapeo': '2026-11-22 08:00' },
      { Tienda: 'Estilos', Marca: 'ONE', Modelo: 'Juan', Precio: 169.9, Moneda: 'PEN', URL: 'https://b', 'Fecha de scrapeo': '2026-11-23 08:00' },
    ]);
    const libro = utils.book_new();
    utils.book_append_sheet(libro, hoja, 'zapatillas');
    const buffer = write(libro, { type: 'array', bookType: 'xlsx' }) as ArrayBuffer;
    const productos = leerExcel(buffer);
    expect(productos).toHaveLength(2);
    expect(productos[0]).toMatchObject({ tienda: 'Oechsle', marca: 'NIKE', precio: 499.9 });
    expect(ultimaFecha(productos)).toBe('2026-11-23 08:00');
  });
});
