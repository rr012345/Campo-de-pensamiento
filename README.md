# CORPUS / GRAFOS
## Red de obras con premisas conceptuales generadas por cadena de Markov
### Rosemberg Sandoval

Visualización interactiva en el navegador. No requiere instalar nada.

---

### Estructura

```
artfacto-web/
├── app.py              ← servidor Flask (API Markov)
├── requirements.txt
├── Procfile            ← para Railway
├── static/
│   └── index.html      ← visualización p5.js
├── obra.csv
├── Corpus_Espacio.csv
├── cuerpo.csv
├── teoria.txt
├── performance.txt
├── materialidad.txt
└── politica.txt
```

---

### Deploy en Railway

1. Sube este repo a GitHub
2. Ve a [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Selecciona el repo → Railway detecta Python automáticamente
4. En ~2 minutos tenés una URL pública

---

### Controles

| Acción | Efecto |
|---|---|
| Click en nodo | Seleccionar, ver conexiones y premisas |
| Arrastrar nodo | Mover libremente |
| `R` | Regenerar todas las relaciones |
| `S` | Guardar captura PNG |
| `+` / `-` | Velocidad de escritura |
| `ESC` | Deseleccionar |

---

### Cómo funciona

- 4 corpus textuales (~76.000 tokens) alimentan una cadena de Markov de orden 3
- Cada relación entre obras lleva una premisa conceptual generada por la cadena
- Las premisas mutan cada 1.6 segundos y se regeneran completas cada 20 segundos
- Las conexiones se calculan por afinidad semántica entre capas: espacio, cuerpo, objetos
