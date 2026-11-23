# Comparador de precios de zapatillas (Examen Final E-Commerce UTEC 2026-2)

Un agente de IA en n8n scrapea precios de zapatillas en tres tiendas peruanas (Oechsle, Footloose y Estilos), genera `zapatillas.xlsx`, avisa por correo cada etapa y publica el Excel en este repositorio. Una web en Vercel lee ese Excel y permite buscar precios ordenados por BM25.

- Repositorio: https://github.com/aaronvanoordt-vanar/examen-final-zapatillas
- Web en Vercel: https://web-zeta-taupe-22.vercel.app

## Arquitectura

```
Trigger (manual / diario 8am)
  -> Configuración (3 tiendas + URLs)
  -> AI Agent (NVIDIA Nemotron) --usa--> HTTP Request Tool (API de catálogo VTEX)
  -> Limpiar y deduplicar (precio numérico, sin espacios, sin duplicados, registra tiendas caídas)
  -> Correo [Examen Final - Scrapeo]
  -> zapatillas.xlsx -> disco + correo [Examen Final - Excel] con adjunto
                     -> GitHub, rama `datos` (cada ejecución lo actualiza)
Web (Vercel) -> lee zapatillas.xlsx de la rama `datos` -> catálogo + buscador BM25
Workflow de alertas (Error Trigger) -> correo cuando falla el principal
```

## Estructura

| Ruta | Contenido |
|---|---|
| `docker-compose.yml` | Stack n8n 2.45.7 + PostgreSQL 17 (versiones fijas, volúmenes, puertos en 127.0.0.1) |
| `.env.example` | Variables necesarias, sin claves reales (copiar a `.env`) |
| `workflows/workflow-scraping.json` | Workflow principal |
| `workflows/workflow-alertas.json` | Workflow de alerta por correo |
| `workflows/generar_workflows.py` | Script que genera los dos JSON |
| `web/` | Web Vite + TypeScript: BM25 (`src/bm25.ts`), lectura del Excel (`src/datos.ts`), pruebas (`tests/`) |
| `.github/workflows/ci.yml` | Pipeline: instalar, lint, pruebas y build en cada PR y push a `main` |
| rama `datos` | `zapatillas.xlsx` que publica n8n |

## 1. Levantar el stack

Requisitos: Docker Desktop.

```bash
cp .env.example .env   # cambiar POSTGRES_PASSWORD y N8N_ENCRYPTION_KEY
docker compose up -d
docker compose ps
```

n8n queda en http://localhost:5678 (solo accesible desde 127.0.0.1) y guarda sus datos en PostgreSQL. Los datos sobreviven a `docker compose down` gracias a los volúmenes `postgres_data` y `n8n_data`.

## 2. Importar los workflows

```bash
docker compose cp workflows/workflow-alertas.json n8n:/tmp/a.json
docker compose cp workflows/workflow-scraping.json n8n:/tmp/s.json
docker compose exec n8n n8n import:workflow --input=/tmp/a.json
docker compose exec n8n n8n import:workflow --input=/tmp/s.json
```

También se pueden importar desde la interfaz de n8n con **Import from File**. Luego, en n8n:

1. Crear las credenciales **NVIDIA API** (API key de build.nvidia.com), **SMTP** (Gmail con contraseña de aplicación, `smtp.gmail.com:465`, SSL) y **GitHub API** (token con permiso Contents read/write sobre este repositorio).
2. Asignarlas a los nodos `NVIDIA Nemotron`, `Correo scrapeo`, `Correo Excel`, `Publicar Excel en GitHub` y `Correo de alerta`.
3. Revisar el nodo `Configuración` (nombre, correos, repositorio y URLs de las tiendas).
4. Publicar ambos workflows. El principal ya tiene configurado el workflow de alertas como *Error Workflow*.

Ninguna clave está escrita en los nodos: todas viven en credenciales de n8n.

## 3. Desplegar la web

```bash
cd web
npm ci
npm run dev      # desarrollo local
npm run lint && npm test && npm run build
```

En Vercel: **Add New Project** -> importar este repositorio -> **Root Directory: `web`** (framework Vite detectado automáticamente) -> **Deploy**. Cada push a `main` vuelve a desplegar. La web descarga `zapatillas.xlsx` de la rama `datos` en cada visita, así que muestra los datos nuevos apenas n8n termina, sin redeploy.

## Búsqueda BM25

`web/src/bm25.ts` implementa BM25 (k1 = 1.2, b = 0.75, IDF de Lucene) sobre marca, modelo y tienda. Antes de indexar y de buscar, el texto se pasa a minúsculas y se le quitan las tildes, así que `ZAPATILLAS ATLÉTICO` y `zapatillas atletico` devuelven lo mismo. Los resultados se ordenan por puntaje; si dos productos empatan (el mismo modelo en dos tiendas), sale primero el más barato. Las pruebas en `web/tests/bm25.test.ts` verifican el orden para consultas conocidas.

## Pipeline y rama protegida

`.github/workflows/ci.yml` corre en cada pull request hacia `main` y en cada push a `main`: `npm ci`, `npm run lint`, `npm test` y `npm run build`. Si un paso falla, el job `lint-test-build` falla. La rama `main` exige que ese check pase (también para administradores), así que un PR con el pipeline en rojo no se puede fusionar.
