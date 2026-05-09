"""
app.py — Corpus / Grafos — Rosemberg Sandoval
Versión para Railway/web: sirve la visualización + API Markov
"""

import os, re, json, random, time, csv, threading, math
from collections import defaultdict
from flask import Flask, jsonify, send_from_directory

# ── CONFIG ────────────────────────────────────────────────────────────────────

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CORPUS_FILES  = ["teoria.txt", "performance.txt", "materialidad.txt", "politica.txt"]
OBRA_CSV      = os.path.join(BASE_DIR, "obra.csv")
ESPACIO_CSV   = os.path.join(BASE_DIR, "Corpus_Espacio.csv")
CUERPO_CSV    = os.path.join(BASE_DIR, "cuerpo.csv")
PORT          = int(os.environ.get("PORT", 5050))
MARKOV_ORDER  = 3
PREMISA_MIN   = 20
PREMISA_MAX   = 45
REGEN_INTERVAL = 20
REL_MIN = 300
REL_MAX = 700

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["JSON_ENSURE_ASCII"] = False

state = {
    "obras": [], "relaciones": [],
    "cadena": {}, "inicios": [],
    "af_espacio": {}, "af_cuerpo": {}, "af_objetos": {},
    "last_regen": 0, "corpus_tokens": 0,
    "n_relaciones_objetivo": 450,
    "ready": False,
}
lock = threading.Lock()

# ── CORPUS TEXTUAL ────────────────────────────────────────────────────────────

def leer_corpus(dirpath):
    textos = []
    for fname in CORPUS_FILES:
        fpath = os.path.join(dirpath, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath, encoding="utf-8", errors="ignore") as f:
            textos.append(f.read())
    return "\n".join(textos)

def tokenizar(texto):
    oraciones = []
    for linea in texto.split("\n"):
        palabras = re.findall(r"[A-Za-záéíóúüñÁÉÍÓÚÜÑ'\-]{2,}", linea.lower())
        if len(palabras) >= MARKOV_ORDER + 2:
            oraciones.append(palabras)
    return oraciones

def construir_cadena(oraciones):
    cadena  = defaultdict(list)
    inicios = []
    for palabras in oraciones:
        inicios.append(tuple(palabras[:MARKOV_ORDER]))
        for i in range(len(palabras) - MARKOV_ORDER):
            clave = tuple(palabras[i:i + MARKOV_ORDER])
            cadena[clave].append(palabras[i + MARKOV_ORDER])
    return dict(cadena), inicios

def generar_premisa(cadena, inicios):
    signos_cierre = {
        'de','del','en','el','la','los','las','un','una',
        'y','que','como','con','por','para','se','su','sus','a','al'
    }
    for _ in range(60):
        inicio    = random.choice(inicios)
        resultado = list(inicio)
        clave     = inicio
        for _ in range(PREMISA_MAX - MARKOV_ORDER):
            sig = cadena.get(clave)
            if not sig:
                break
            resultado.append(random.choice(sig))
            clave = tuple(resultado[-MARKOV_ORDER:])
        if len(resultado) < PREMISA_MIN:
            continue
        if len(resultado) > PREMISA_MAX:
            resultado = resultado[:PREMISA_MAX]
        for back in range(min(8, len(resultado) - PREMISA_MIN)):
            if resultado[-(back+1)] not in signos_cierre:
                if back > 0:
                    resultado = resultado[:len(resultado)-back]
                break
        frase = " ".join(resultado)
        return frase[0].upper() + frase[1:]
    return "El cuerpo como territorio político atravesado por la violencia y el ritual"

# ── UTILIDAD ──────────────────────────────────────────────────────────────────

def nombre_palabras(nombre):
    limpio = re.sub(r'\W+', ' ', nombre.lower()).strip()
    return {w for w in limpio.split() if len(w) > 3}

def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0

# ── CAPAS ─────────────────────────────────────────────────────────────────────

def leer_espacio(csv_path):
    mapa = {}
    if not os.path.exists(csv_path):
        return mapa
    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            partes   = row['image'].replace('\\', '/').split('/')
            obra_dir = partes[-2].strip().lower() if len(partes) >= 2 else ""
            labels   = {l.strip() for l in row['labels'].split(';') if l.strip()}
            if obra_dir:
                if obra_dir not in mapa:
                    mapa[obra_dir] = set()
                mapa[obra_dir].update(labels)
    return mapa

def leer_cuerpo(cuerpo_path, espacio_path):
    mapa = {}
    if not os.path.exists(cuerpo_path) or not os.path.exists(espacio_path):
        return mapa
    imgs_order = []
    visto = set()
    with open(espacio_path, encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            img = row["image"]
            if img not in visto:
                visto.add(img)
                obra_dir = img.replace("\\", "/").split("/")[-2].strip().lower()
                imgs_order.append(obra_dir)
    hash_labels = {}
    hash_order  = []
    with open(cuerpo_path, encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            h = row.get("archivo", "").split("_")[0].strip()
            if not h:
                continue
            if h not in hash_labels:
                hash_labels[h] = set()
                hash_order.append(h)
            parte = row.get("parte_cuerpo", "").strip().lower()
            if parte:
                hash_labels[h].add(parte)
            for col in ["label_1","label_2","label_3","label_4","label_5"]:
                val = row.get(col, "").strip().lower()
                if val and val != "nan" and len(val) > 2:
                    hash_labels[h].add(val)
    n = min(len(imgs_order), len(hash_order))
    for i in range(n):
        obra_dir = imgs_order[i]
        labels   = hash_labels[hash_order[i]]
        if obra_dir not in mapa:
            mapa[obra_dir] = set()
        mapa[obra_dir].update(labels)
    return mapa

def leer_objetos(csv_path):
    mapa = {}
    if not os.path.exists(csv_path):
        return mapa
    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            oid   = int(row.get("id", 0))
            raw   = row.get("objetos", "") or ""
            items = re.findall(r"'([^']+)'", raw)
            mapa[oid] = frozenset(i.strip().lower() for i in items if i.strip())
    return mapa

def leer_obras(csv_path):
    obras = []
    if not os.path.exists(csv_path):
        return obras
    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            obras.append({
                "id":     int(row.get("id", 0)),
                "titulo": (row.get("obra", "") or "").strip(),
                "obra":   (row.get("obra", "") or "").strip(),
                "year":   (row.get("año",  "") or "").strip(),
                "año":    (row.get("año",  "") or "").strip(),
                "texto":  (row.get("descripcion_01", "") or "").strip()[:500],
            })
    return obras

def afinidades_desde_mapa_dir(obras, label_map_dir):
    obra_labels = {}
    for obra in obras:
        oid = obra["id"]
        pw  = nombre_palabras(obra["titulo"])
        labels = set()
        for dir_name, dir_labels in label_map_dir.items():
            if pw & nombre_palabras(dir_name):
                labels.update(dir_labels)
        obra_labels[oid] = frozenset(labels)
    ids = [o["id"] for o in obras]
    af  = {}
    for i in range(len(ids)):
        for j in range(i+1, len(ids)):
            a, b = ids[i], ids[j]
            s = jaccard(obra_labels.get(a, frozenset()), obra_labels.get(b, frozenset()))
            if s > 0:
                af[(min(a,b), max(a,b))] = round(0.2 + 0.8 * s, 3)
    return af

def afinidades_desde_objetos(obras, objetos_map):
    ids = [o["id"] for o in obras]
    af  = {}
    for i in range(len(ids)):
        for j in range(i+1, len(ids)):
            a, b = ids[i], ids[j]
            s = jaccard(objetos_map.get(a, frozenset()), objetos_map.get(b, frozenset()))
            if s > 0:
                af[(min(a,b), max(a,b))] = round(0.2 + 0.8 * s, 3)
    return af

def tipo_y_score(par, af_e, af_c, af_o):
    se = af_e.get(par, 0)
    sc = af_c.get(par, 0)
    so = af_o.get(par, 0)
    mx = max(se, sc, so)
    if mx == 0:
        return "general", round(random.uniform(0.15, 0.4), 3)
    activas = [s for s in [se, sc, so] if s > 0]
    if len(activas) >= 2:
        return "mixto", round(sum(activas) / len(activas), 3)
    if se >= sc and se >= so: return "espacio", se
    if sc >= se and sc >= so: return "cuerpo",  sc
    return "objetos", so

def calcular_n():
    val = (random.random() + random.random() + random.random()) / 3.0
    n   = int(REL_MIN + (REL_MAX - REL_MIN) * val)
    return max(REL_MIN, min(REL_MAX, n))

def generar_relaciones(obras, cadena, inicios, af_e, af_c, af_o, n_obj):
    if len(obras) < 2:
        return []
    ids    = [o["id"] for o in obras]
    usados = set()
    rels   = []
    todos = set(af_e.keys()) | set(af_c.keys()) | set(af_o.keys())
    ordenados = sorted(todos,
        key=lambda p: af_e.get(p,0) + af_c.get(p,0) + af_o.get(p,0),
        reverse=True)
    for par in ordenados:
        if len(rels) >= n_obj: break
        a, b = par
        if a not in ids or b not in ids: continue
        if par in usados: continue
        usados.add(par)
        tipo, score = tipo_y_score(par, af_e, af_c, af_o)
        rels.append({"A":a,"B":b,"premisa":generar_premisa(cadena,inicios),"score":score,"tipo":tipo})
    conx = defaultdict(int)
    for r in rels:
        conx[r["A"]] += 1; conx[r["B"]] += 1
    random.shuffle(ids)
    for oid in ids:
        while conx[oid] < 2 and len(rels) < n_obj:
            candidatos = [x for x in ids if x != oid]
            random.shuffle(candidatos)
            for otro in candidatos:
                par = (min(oid,otro), max(oid,otro))
                if par not in usados:
                    usados.add(par)
                    tipo, score = tipo_y_score(par, af_e, af_c, af_o)
                    rels.append({"A":oid,"B":otro,"premisa":generar_premisa(cadena,inicios),"score":score,"tipo":tipo})
                    conx[oid] += 1; conx[otro] += 1
                    break
            else: break
    intentos = 0
    while len(rels) < n_obj and intentos < n_obj * 10:
        intentos += 1
        a, b = random.sample(ids, 2)
        par  = (min(a,b), max(a,b))
        if par in usados: continue
        usados.add(par)
        tipo, score = tipo_y_score(par, af_e, af_c, af_o)
        rels.append({"A":a,"B":b,"premisa":generar_premisa(cadena,inicios),"score":score,"tipo":tipo})
    return rels

def regenerar():
    with lock:
        cadena = state["cadena"]; inicios = state["inicios"]
        obras  = state["obras"]
        af_e   = state["af_espacio"]; af_c = state["af_cuerpo"]; af_o = state["af_objetos"]
        if not obras or not cadena: return
        n = calcular_n()
        state["n_relaciones_objetivo"] = n
        state["relaciones"] = generar_relaciones(obras, cadena, inicios, af_e, af_c, af_o, n)
        state["last_regen"] = time.time()

def loop_regeneracion():
    while True:
        time.sleep(REGEN_INTERVAL)
        regenerar()

def init_state():
    print("[1] Corpus...")
    texto     = leer_corpus(BASE_DIR)
    oraciones = tokenizar(texto)
    total_tok = sum(len(o) for o in oraciones)
    print(f"  {len(oraciones)} oraciones / {total_tok} tokens")

    print("[2] Cadena Markov orden 3...")
    cadena, inicios = construir_cadena(oraciones)

    print("[3] Obras...")
    obras = leer_obras(OBRA_CSV)

    print("[4] Capas semánticas...")
    espacio_map = leer_espacio(ESPACIO_CSV)
    af_espacio  = afinidades_desde_mapa_dir(obras, espacio_map)
    cuerpo_map  = leer_cuerpo(CUERPO_CSV, ESPACIO_CSV)
    af_cuerpo   = afinidades_desde_mapa_dir(obras, cuerpo_map)
    objetos_map = leer_objetos(OBRA_CSV)
    af_objetos  = afinidades_desde_objetos(obras, objetos_map)

    print("[5] Relaciones iniciales...")
    n_ini = calcular_n()
    rels  = generar_relaciones(obras, cadena, inicios, af_espacio, af_cuerpo, af_objetos, n_ini)

    with lock:
        state["cadena"]                = cadena
        state["inicios"]               = inicios
        state["obras"]                 = obras
        state["relaciones"]            = rels
        state["af_espacio"]            = af_espacio
        state["af_cuerpo"]             = af_cuerpo
        state["af_objetos"]            = af_objetos
        state["corpus_tokens"]         = total_tok
        state["last_regen"]            = time.time()
        state["n_relaciones_objetivo"] = n_ini
        state["ready"]                 = True
    print(f"[OK] {len(obras)} obras, {len(rels)} relaciones — servidor listo")

# ── CORS ──────────────────────────────────────────────────────────────────────

def cors(r):
    r.headers["Access-Control-Allow-Origin"] = "*"
    return r

# ── RUTAS API ─────────────────────────────────────────────────────────────────

@app.route("/obras")
def ep_obras():
    with lock: data = state["obras"]
    return cors(jsonify(data))

@app.route("/relaciones")
def ep_relaciones():
    with lock: data = state["relaciones"]
    return cors(jsonify(data))

@app.route("/regenerar")
def ep_regenerar():
    regenerar()
    with lock: n = len(state["relaciones"])
    return cors(jsonify({"ok": True, "relaciones": n}))

@app.route("/premisa")
def ep_premisa():
    with lock: cadena = state["cadena"]; inicios = state["inicios"]
    return cors(jsonify({"premisa": generar_premisa(cadena, inicios)}))

@app.route("/status")
def ep_status():
    with lock:
        tipos = defaultdict(int)
        for r in state["relaciones"]: tipos[r.get("tipo","?")] += 1
        return cors(jsonify({
            "ready": state["ready"],
            "obras": len(state["obras"]),
            "relaciones": len(state["relaciones"]),
            "tipos": dict(tipos),
            "cadena_keys": len(state["cadena"]),
        }))

# ── RUTA PRINCIPAL ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    threading.Thread(target=init_state, daemon=True).start()
    threading.Thread(target=loop_regeneracion, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
else:
    # Para gunicorn
    threading.Thread(target=init_state, daemon=True).start()
    threading.Thread(target=loop_regeneracion, daemon=True).start()
