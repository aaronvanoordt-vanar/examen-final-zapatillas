"""Genera workflow-scraping.json y workflow-alertas.json para importar en n8n 2.45.7.

Uso: python3 workflows/generar_workflows.py
Ninguna clave va aqui: NVIDIA, SMTP y GitHub se asignan como credenciales en n8n.
"""
import json
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent
MAIN_ID = "ZapScrapeMain001"
ALERT_ID = "ZapAlertasErr001"

NOMBRE = "Aarón Carlo Van Oordt Arbulú"
CORREO_REMITENTE = "aaron.vanoordt@utec.edu.pe"
# MODO_PRUEBA = True envia todo al remitente; poner False para las ejecuciones finales al docente.
MODO_PRUEBA = False
CORREO_DOCENTE = CORREO_REMITENTE if MODO_PRUEBA else "kneira@utec.edu.pe"

CONFIG_JS = r"""// Configuracion central del workflow (sin claves: las claves viven en credenciales de n8n).
// Caso 2 (tienda caida): cambia la url de una tienda por una inexistente, por ejemplo
// https://www.tienda-que-no-existe-xyz.pe/api/catalog_system/pub/products/search?ft=zapatillas
const general = {
  nombre: '__NOMBRE__',
  correoDocente: '__DOCENTE__',      // para pruebas puedes poner tu propio correo
  correoRemitente: '__REMITENTE__',  // el mismo Gmail de la credencial SMTP
  githubOwner: 'aaronvanoordt-vanar',
  githubRepo: 'examen-final-zapatillas',
  githubRama: 'datos',
  githubRuta: 'zapatillas.xlsx',
};

const consulta = 'ft=zapatillas%20running&_from=0&_to=19';
const tiendas = [
  { tienda: 'Oechsle',   empresa: 'Tiendas Peruanas S.A. (Intercorp)', url: `https://www.oechsle.pe/api/catalog_system/pub/products/search?${consulta}` },
  { tienda: 'Footloose', empresa: 'Footloose S.A.C.',                  url: `https://www.footloose.pe/api/catalog_system/pub/products/search?${consulta}` },
  { tienda: 'Estilos',   empresa: 'Estilos S.R.L.',                    url: `https://www.estilos.com.pe/api/catalog_system/pub/products/search?${consulta}` },
];

// Pruebas por webhook de produccion (workflow publicado):
//   ?tiendaCaida=Oechsle  -> esa tienda apunta a un dominio inexistente (caso 2)
//   ?fallar=todas         -> las tres fallan y se dispara el workflow de alertas
const q = ($input.first().json.query) || {};
const caida = String(q.tiendaCaida || '').toLowerCase();
for (const t of tiendas) {
  if (q.fallar === 'todas' || t.tienda.toLowerCase() === caida) {
    t.url = `https://www.${t.tienda.toLowerCase()}-tienda-inexistente-xyz.pe/api/catalog_system/pub/products/search?${consulta}`;
  }
}

return tiendas.map(t => ({ json: { ...t, ...general } }));
""".replace("__NOMBRE__", NOMBRE).replace("__DOCENTE__", CORREO_DOCENTE).replace("__REMITENTE__", CORREO_REMITENTE)

SYSTEM_MSG = """Eres un agente de scraping de precios de zapatillas en tiendas online de Peru.

Reglas:
1. Usa SIEMPRE la herramienta obtener_productos con la URL exacta que te da el usuario. No inventes URLs.
2. La herramienta devuelve una lista JSON de productos con: productName, brand, link e items[0].sellers[0].commertialOffer.Price.
3. Extrae TODOS los productos que devuelva la herramienta (minimo 10 si existen). Nunca inventes productos ni precios.
4. Para cada producto: marca = brand; modelo = productName; precio = Price (numero en soles, sin simbolos); url = link.
5. Si la herramienta devuelve un error, no responde o la lista viene vacia, responde con estado "error" y explica el motivo en "error".
6. Responde UNICAMENTE con JSON valido, sin texto adicional ni bloques de codigo, con esta forma:
{"tienda": "<nombre>", "estado": "ok" | "error", "error": "<motivo o vacio>", "productos": [{"marca": "...", "modelo": "...", "precio": 199.9, "url": "https://..."}]}"""

AGENT_TEXT = """=Tienda: {{ $json.tienda }}
URL de la API de catalogo: {{ $json.url }}

Obten los productos de esta tienda con la herramienta obtener_productos usando exactamente esa URL y devuelve el JSON pedido."""

LIMPIAR_JS = r"""// Limpieza, validacion y deduplicacion de lo que devolvio el agente para cada tienda.
const config = $('Configuración').all().map(i => i.json);
const salidas = $input.all();
const ahora = new Date();
const fecha = ahora.toLocaleString('sv-SE', { timeZone: 'America/Lima' }).slice(0, 16); // YYYY-MM-DD HH:mm

const limpiarTexto = v => String(v ?? '').replace(/\s+/g, ' ').trim();

function parsePrecio(v) {
  if (typeof v === 'number') return Math.round(v * 100) / 100;
  let s = String(v ?? '').replace(/S\/\.?|PEN|soles?/gi, '').replace(/[^\d.,-]/g, '').trim();
  if (!s) return NaN;
  if (s.includes(',') && s.includes('.')) s = s.replace(/,/g, '');          // 1,299.90
  else if (s.includes(',') && /,\d{1,2}$/.test(s)) s = s.replace(',', '.');   // 1299,90
  else s = s.replace(/,/g, '');                                              // 1,299
  const n = parseFloat(s);
  return Number.isFinite(n) ? Math.round(n * 100) / 100 : NaN;
}

function parseAgente(out) {
  if (out && typeof out === 'object') return out;
  let txt = String(out ?? '').replace(/<think>[\s\S]*?<\/think>/gi, '').replace(/```(?:json)?/gi, '').trim();
  const a = txt.indexOf('{'), b = txt.lastIndexOf('}');
  if (a >= 0 && b > a) { try { return JSON.parse(txt.slice(a, b + 1)); } catch (e) {} }
  const c = txt.indexOf('['), d = txt.lastIndexOf(']');
  if (c >= 0 && d > c) { try { return { estado: 'ok', productos: JSON.parse(txt.slice(c, d + 1)) }; } catch (e) {} }
  return null;
}

const productos = [];
const resumen = {};
const fallidas = [];
const vistos = new Set();

salidas.forEach((item, idx) => {
  const pi = item.pairedItem;
  const cfgIdx = Array.isArray(pi) ? (pi[0]?.item ?? idx) : (pi?.item ?? idx);
  const cfg = config[cfgIdx] ?? config[idx];
  const tienda = cfg.tienda;
  resumen[tienda] = 0;

  if (item.json.error) {
    const msg = typeof item.json.error === 'string' ? item.json.error : (item.json.error.message || JSON.stringify(item.json.error));
    fallidas.push({ tienda, url: cfg.url, motivo: limpiarTexto(msg).slice(0, 300) });
    return;
  }
  const data = parseAgente(item.json.output);
  if (!data) {
    fallidas.push({ tienda, url: cfg.url, motivo: 'El agente no devolvio un JSON valido' });
    return;
  }
  if (data.estado === 'error') {
    fallidas.push({ tienda, url: cfg.url, motivo: limpiarTexto(data.error || 'La herramienta devolvio un error') });
    return;
  }
  const origen = (String(cfg.url).match(/^https?:\/\/[^/]+/i) || [''])[0];
  for (const p of (Array.isArray(data.productos) ? data.productos : [])) {
    const precio = parsePrecio(p.precio);
    let url = limpiarTexto(p.url);
    if (url && !/^https?:\/\//i.test(url)) url = origen + (url.startsWith('/') ? '' : '/') + url;
    const marca = limpiarTexto(p.marca).toUpperCase();
    const modelo = limpiarTexto(p.modelo);
    if (!marca || !modelo || !url || !(precio > 0)) continue;
    const claveUrl = url.split('?')[0].toLowerCase();
    const claveProd = `${tienda}|${marca}|${modelo}|${precio}`.toLowerCase();
    if (vistos.has(claveUrl) || vistos.has(claveProd)) continue;
    vistos.add(claveUrl); vistos.add(claveProd);
    productos.push({ tienda, marca, modelo, precio, moneda: 'PEN', url, fecha });
    resumen[tienda]++;
  }
  if (resumen[tienda] === 0) {
    fallidas.push({ tienda, url: cfg.url, motivo: 'La tienda no devolvio productos validos' });
  }
});

const filas = Object.entries(resumen).map(([t, n]) => `<tr><td>${t}</td><td style="text-align:right">${n}</td></tr>`).join('');
const fallidasHtml = fallidas.length
  ? `<ul>${fallidas.map(f => `<li><b>${f.tienda}</b>: ${f.motivo}<br><small>${f.url}</small></li>`).join('')}</ul>`
  : '<p>Ninguna tienda fallo.</p>';
const resumenHtml = `<h2>Resultado del scrapeo de zapatillas</h2>
<p>Fecha de scrapeo: <b>${fecha}</b> (America/Lima)</p>
<table border="1" cellpadding="6" cellspacing="0"><tr><th>Tienda</th><th>Productos</th></tr>${filas}
<tr><th>Total</th><th style="text-align:right">${productos.length}</th></tr></table>
<h3>Tiendas que fallaron</h3>${fallidasHtml}
<p>Generado por el agente de IA en n8n.</p>`;

return [{ json: { fecha, total: productos.length, resumen, fallidas, productos, resumenHtml } }];
"""

FILAS_JS = r"""// Una fila por producto con las columnas exactas pedidas para zapatillas.xlsx
return $('Limpiar y deduplicar').first().json.productos.map(p => ({
  json: {
    'Tienda': p.tienda,
    'Marca': p.marca,
    'Modelo': p.modelo,
    'Precio': p.precio,
    'Moneda': p.moneda,
    'URL': p.url,
    'Fecha de scrapeo': p.fecha,
  },
}));
"""

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
CFG = "$('Configuración').first().json"


def node(name, ntype, version, pos, params, **extra):
    n = {"parameters": params, "name": name, "type": ntype, "typeVersion": version, "position": pos}
    n["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "examen-final/" + name))
    n.update(extra)
    return n


main_nodes = [
    node("Ejecutar manualmente", "n8n-nodes-base.manualTrigger", 1, [0, 0], {}),
    node("Cada día 8am", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 200],
         {"rule": {"interval": [{"triggerAtHour": 8}]}}),
    node("Webhook producción", "n8n-nodes-base.webhook", 2, [0, 400],
         {"httpMethod": "GET", "path": "scrapeo-zapatillas", "responseMode": "onReceived", "options": {}},
         webhookId="6f1d2c3a-5b4e-4f7a-9c8d-1e2f3a4b5c6d"),
    node("Configuración", "n8n-nodes-base.code", 2, [240, 100], {"jsCode": CONFIG_JS}),
    node("Agente Scraper", "@n8n/n8n-nodes-langchain.agent", 3, [500, 100],
         {"promptType": "define", "text": AGENT_TEXT,
          "options": {"systemMessage": SYSTEM_MSG, "maxIterations": 5, "returnIntermediateSteps": True}},
         onError="continueRegularOutput", retryOnFail=True, maxTries=2, waitBetweenTries=3000),
    node("NVIDIA Nemotron", "@n8n/n8n-nodes-langchain.lmChatNvidia", 1, [420, 340],
         {"model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "options": {"temperature": 0.1, "maxTokens": 16000, "timeout": 300000}}),
    node("obtener_productos", "n8n-nodes-base.httpRequestTool", 4.2, [640, 340],
         {"descriptionType": "manual",
          "toolDescription": "Descarga el catalogo de zapatillas de una tienda online. Recibe la URL completa de la API de catalogo y devuelve una lista JSON de productos con productName, brand, link y el precio en items[0].sellers[0].commertialOffer.Price.",
          "url": "={{ $fromAI('url', 'URL completa de la API de catalogo de la tienda, exactamente como la dio el usuario', 'string') }}",
          "sendHeaders": True,
          "headerParameters": {"parameters": [{"name": "User-Agent", "value": UA}, {"name": "Accept", "value": "application/json"}]},
          "options": {"timeout": 20000},
          "optimizeResponse": True, "responseType": "json", "fieldsToInclude": "selected",
          "fields": "productName,brand,link,items[0].sellers[0].commertialOffer.Price"}),
    node("Limpiar y deduplicar", "n8n-nodes-base.code", 2, [800, 100], {"jsCode": LIMPIAR_JS}),
    node("Correo scrapeo", "n8n-nodes-base.emailSend", 2.1, [1040, 100],
         {"fromEmail": f"={{{{ {CFG}.correoRemitente }}}}",
          "toEmail": f"={{{{ {CFG}.correoDocente }}}}",
          "subject": f"=[Examen Final - Scrapeo] {{{{ {CFG}.nombre }}}} - {{{{ $json.total }}}} zapatillas",
          "emailFormat": "html", "html": "={{ $json.resumenHtml }}", "options": {}}),
    node("¿Hay productos?", "n8n-nodes-base.if", 2.2, [1260, 100],
         {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                         "conditions": [{"id": "c1", "leftValue": "={{ $('Limpiar y deduplicar').first().json.total }}",
                                         "rightValue": 0, "operator": {"type": "number", "operation": "gt"}}],
                         "combinator": "and"}, "looseTypeValidation": True, "options": {}}),
    node("Todas las tiendas fallaron", "n8n-nodes-base.stopAndError", 1, [1480, 260],
         {"errorMessage": "Ninguna tienda devolvio productos. Revisa las URLs y la credencial de NVIDIA."}),
    node("Filas Excel", "n8n-nodes-base.code", 2, [1480, 0], {"jsCode": FILAS_JS}),
    node("Crear zapatillas.xlsx", "n8n-nodes-base.convertToFile", 1.1, [1700, 0],
         {"operation": "xlsx", "options": {"fileName": "zapatillas.xlsx", "sheetName": "zapatillas", "headerRow": True}}),
    node("Guardar en disco", "n8n-nodes-base.readWriteFile", 1, [1920, -100],
         {"operation": "write", "fileName": "/home/node/.n8n-files/zapatillas.xlsx", "dataPropertyName": "data", "options": {}}),
    node("Correo Excel", "n8n-nodes-base.emailSend", 2.1, [2140, -100],
         {"fromEmail": f"={{{{ {CFG}.correoRemitente }}}}",
          "toEmail": f"={{{{ {CFG}.correoDocente }}}}",
          "subject": f"=[Examen Final - Excel] {{{{ {CFG}.nombre }}}} - zapatillas.xlsx listo",
          "emailFormat": "html",
          "html": "=<p>Adjunto el archivo <b>zapatillas.xlsx</b> generado por el workflow.</p><p>Productos: <b>{{ $('Limpiar y deduplicar').first().json.total }}</b> | Fecha de scrapeo: <b>{{ $('Limpiar y deduplicar').first().json.fecha }}</b></p><p>Columnas: Tienda, Marca, Modelo, Precio, Moneda, URL, Fecha de scrapeo.</p>",
          "options": {"attachments": "data"}}),
    node("Publicar Excel en GitHub", "n8n-nodes-base.github", 1.1, [1920, 120],
         {"resource": "file", "operation": "edit",
          "owner": {"__rl": True, "mode": "name", "value": f"={{{{ {CFG}.githubOwner }}}}"},
          "repository": {"__rl": True, "mode": "name", "value": f"={{{{ {CFG}.githubRepo }}}}"},
          "filePath": f"={{{{ {CFG}.githubRuta }}}}",
          "binaryData": True, "binaryPropertyName": "data",
          "commitMessage": "=datos: zapatillas.xlsx {{ $('Limpiar y deduplicar').first().json.fecha }} ({{ $('Limpiar y deduplicar').first().json.total }} productos)",
          "additionalParameters": {"branch": {"branch": f"={{{{ {CFG}.githubRama }}}}"}}}),
]

main_conn = {
    "Ejecutar manualmente": {"main": [[{"node": "Configuración", "type": "main", "index": 0}]]},
    "Webhook producción": {"main": [[{"node": "Configuración", "type": "main", "index": 0}]]},
    "Cada día 8am": {"main": [[{"node": "Configuración", "type": "main", "index": 0}]]},
    "Configuración": {"main": [[{"node": "Agente Scraper", "type": "main", "index": 0}]]},
    "NVIDIA Nemotron": {"ai_languageModel": [[{"node": "Agente Scraper", "type": "ai_languageModel", "index": 0}]]},
    "obtener_productos": {"ai_tool": [[{"node": "Agente Scraper", "type": "ai_tool", "index": 0}]]},
    "Agente Scraper": {"main": [[{"node": "Limpiar y deduplicar", "type": "main", "index": 0}]]},
    "Limpiar y deduplicar": {"main": [[{"node": "Correo scrapeo", "type": "main", "index": 0}]]},
    "Correo scrapeo": {"main": [[{"node": "¿Hay productos?", "type": "main", "index": 0}]]},
    "¿Hay productos?": {"main": [[{"node": "Filas Excel", "type": "main", "index": 0}],
                                 [{"node": "Todas las tiendas fallaron", "type": "main", "index": 0}]]},
    "Filas Excel": {"main": [[{"node": "Crear zapatillas.xlsx", "type": "main", "index": 0}]]},
    "Crear zapatillas.xlsx": {"main": [[{"node": "Guardar en disco", "type": "main", "index": 0},
                                         {"node": "Publicar Excel en GitHub", "type": "main", "index": 0}]]},
    "Guardar en disco": {"main": [[{"node": "Correo Excel", "type": "main", "index": 0}]]},
}

main_wf = {
    "id": MAIN_ID,
    "name": "Examen Final - Scraping zapatillas",
    "nodes": main_nodes,
    "connections": main_conn,
    "settings": {"executionOrder": "v1", "errorWorkflow": ALERT_ID, "timezone": "America/Lima",
                 "saveManualExecutions": True, "saveDataErrorExecution": "all", "saveDataSuccessExecution": "all"},
    "pinData": {},
    "active": False,
}

ALERT_HTML = """=<h2>Fallo el workflow principal</h2>
<p><b>Workflow:</b> {{ $json.workflow.name }} ({{ $json.workflow.id }})</p>
<p><b>Nodo que fallo:</b> {{ $json.execution.lastNodeExecuted }}</p>
<p><b>Error:</b> {{ $json.execution.error.message }}</p>
<p><b>Ejecucion:</b> {{ $json.execution.id }} - {{ $json.execution.url }}</p>
<p><b>Modo:</b> {{ $json.execution.mode }} | <b>Fecha:</b> {{ $now.setZone('America/Lima').toFormat('yyyy-MM-dd HH:mm') }}</p>"""

alert_nodes = [
    node("Cuando falla un workflow", "n8n-nodes-base.errorTrigger", 1, [0, 0], {}),
    node("Correo de alerta", "n8n-nodes-base.emailSend", 2.1, [260, 0],
         {"fromEmail": CORREO_REMITENTE, "toEmail": CORREO_DOCENTE,
          "subject": f"=[Examen Final - Alerta] {NOMBRE} - Fallo: {{{{ $json.workflow.name }}}}",
          "emailFormat": "html", "html": ALERT_HTML, "options": {}}),
]
alert_wf = {
    "id": ALERT_ID,
    "name": "Examen Final - Alertas de error",
    "nodes": alert_nodes,
    "connections": {"Cuando falla un workflow": {"main": [[{"node": "Correo de alerta", "type": "main", "index": 0}]]}},
    "settings": {"executionOrder": "v1", "timezone": "America/Lima"},
    "pinData": {},
    "active": False,
}

# Referencias a credenciales de n8n (solo id y nombre; las claves quedan cifradas en n8n).
CREDENCIALES = {
    "@n8n/n8n-nodes-langchain.lmChatNvidia": ("nvidiaApi", "0tdsVDbjmSS9huS9", "NVIDIA Nemotron account"),
    "n8n-nodes-base.emailSend": ("smtp", "IpsYsFnpMMCV35TU", "SMTP account"),
    "n8n-nodes-base.github": ("githubApi", "BfFz9DV1hZQ5B5Bp", "GitHub account"),
}
for n in main_nodes + alert_nodes:
    if n["type"] in CREDENCIALES:
        tipo, cid, nombre = CREDENCIALES[n["type"]]
        n["credentials"] = {tipo: {"id": cid, "name": nombre}}

(OUT / "workflow-scraping.json").write_text(json.dumps(main_wf, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "workflow-alertas.json").write_text(json.dumps(alert_wf, ensure_ascii=False, indent=2), encoding="utf-8")
print("ok")
