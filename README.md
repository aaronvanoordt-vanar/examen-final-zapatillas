# Comparador de precios de zapatillas (Examen Final E-Commerce UTEC 2026-2)

Solución que scrapea precios de zapatillas en tres tiendas peruanas (Oechsle, Footloose y Estilos) con un agente de IA en n8n, genera `zapatillas.xlsx`, envía correos en cada etapa y publica una web en Vercel con búsqueda BM25.

## Estructura

| Ruta | Contenido |
|---|---|
| `docker-compose.yml` | Stack n8n 2.45.7 + PostgreSQL 17 |
| `.env.example` | Variables necesarias (copiar a `.env`) |
| `workflows/workflow-scraping.json` | Workflow principal (AI Agent + NVIDIA + HTTP Request Tool) |
| `workflows/workflow-alertas.json` | Workflow de alerta por correo cuando falla el principal |
| `workflows/generar_workflows.py` | Script que genera los dos JSON |
| rama `datos` | `zapatillas.xlsx` publicado por n8n en cada ejecución |

## 1. Levantar el stack

```bash
cp .env.example .env   # editar claves reales
docker compose up -d
docker compose ps
```

n8n queda en http://localhost:5678 (solo 127.0.0.1). Los datos persisten en los volúmenes `postgres_data` y `n8n_data`.

## 2. Importar los workflows

```bash
docker compose cp workflows/workflow-alertas.json n8n:/tmp/a.json
docker compose cp workflows/workflow-scraping.json n8n:/tmp/s.json
docker compose exec n8n n8n import:workflow --input=/tmp/a.json
docker compose exec n8n n8n import:workflow --input=/tmp/s.json
```

Luego, en n8n, crear las credenciales (NVIDIA API, SMTP de Gmail y GitHub API), asignarlas a sus nodos, revisar el nodo `Configuración` y publicar ambos workflows.

## 3. Desplegar la web

Pendiente (se completa en el siguiente paso).

## Enlaces

- Repositorio: https://github.com/aaronvanoordt-vanar/examen-final-zapatillas
- Web en Vercel: pendiente
