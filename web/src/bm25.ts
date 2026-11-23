export interface Producto {
  tienda: string;
  marca: string;
  modelo: string;
  precio: number;
  moneda: string;
  url: string;
  fecha: string;
}

export interface Resultado {
  producto: Producto;
  puntaje: number;
}

/** Minusculas, sin tildes ni signos: "ZAPATILLAS ATLÉTICO" -> "zapatillas atletico". */
export function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export function tokenizar(texto: string): string[] {
  const limpio = normalizar(texto);
  return limpio ? limpio.split(' ') : [];
}

/** Texto indexado de cada producto: marca y modelo (lo pedido) mas la tienda. */
export function textoIndexado(p: Producto): string {
  return `${p.marca} ${p.modelo} ${p.tienda}`;
}

export interface OpcionesBM25 {
  k1?: number;
  b?: number;
}

/**
 * Indice BM25 (Robertson/Sparck Jones, variante de Lucene con IDF siempre positiva):
 * score(D,Q) = sum_q IDF(q) * f(q,D) * (k1 + 1) / (f(q,D) + k1 * (1 - b + b * |D| / avgdl))
 * IDF(q) = ln(1 + (N - n(q) + 0.5) / (n(q) + 0.5))
 */
export class IndiceBM25 {
  private readonly docs: Producto[];
  private readonly frecuencias: Map<string, number>[];
  private readonly largos: number[];
  private readonly df = new Map<string, number>();
  private readonly avgdl: number;
  private readonly k1: number;
  private readonly b: number;

  constructor(productos: Producto[], opciones: OpcionesBM25 = {}) {
    this.k1 = opciones.k1 ?? 1.2;
    this.b = opciones.b ?? 0.75;
    this.docs = productos;
    this.frecuencias = [];
    this.largos = [];
    for (const p of productos) {
      const tokens = tokenizar(textoIndexado(p));
      const tf = new Map<string, number>();
      for (const t of tokens) tf.set(t, (tf.get(t) ?? 0) + 1);
      for (const t of tf.keys()) this.df.set(t, (this.df.get(t) ?? 0) + 1);
      this.frecuencias.push(tf);
      this.largos.push(tokens.length);
    }
    const total = this.largos.reduce((a, n) => a + n, 0);
    this.avgdl = productos.length ? total / productos.length : 0;
  }

  idf(termino: string): number {
    const n = this.df.get(termino) ?? 0;
    const N = this.docs.length;
    return Math.log(1 + (N - n + 0.5) / (n + 0.5));
  }

  puntaje(indice: number, terminos: string[]): number {
    const tf = this.frecuencias[indice];
    const largo = this.largos[indice];
    let score = 0;
    for (const q of terminos) {
      const f = tf.get(q) ?? 0;
      if (!f) continue;
      const denom = f + this.k1 * (1 - this.b + (this.b * largo) / (this.avgdl || 1));
      score += this.idf(q) * ((f * (this.k1 + 1)) / denom);
    }
    return score;
  }

  /** Resultados con puntaje > 0, de mayor a menor puntaje; empate: menor precio primero. */
  buscar(consulta: string, limite = Infinity): Resultado[] {
    const terminos = [...new Set(tokenizar(consulta))];
    if (!terminos.length) return [];
    const resultados: Resultado[] = [];
    this.docs.forEach((producto, i) => {
      const puntaje = this.puntaje(i, terminos);
      if (puntaje > 0) resultados.push({ producto, puntaje });
    });
    resultados.sort(
      (a, b) => b.puntaje - a.puntaje || a.producto.precio - b.producto.precio,
    );
    return resultados.slice(0, limite);
  }
}
