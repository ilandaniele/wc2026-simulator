# WC2026 · Simulador Bayesiano

Simulador Monte Carlo del Mundial 2026. Todo corre en el navegador, sin backend ni internet.

## Archivos

- **`wc2026_simulator.html`** — el simulador. Un solo archivo, autónomo. **Es el sitio.**
- **`retrain.py`** — backend de re-entrenamiento (decaimiento temporal). Regenera el modelo con datos frescos.

## Abrirlo (sitio accesible)

**Opción 1 — directo (más simple):**
Doble click en `wc2026_simulator.html`. Abre en tu navegador y funciona offline.

**Opción 2 — servidor local (red local, ej. verlo desde el celu):**
```bash
cd "C:\Users\Ilan\Desktop\Proyectos\soccer-predictor"
python -m http.server 8000
```
Luego abrí `http://localhost:8000/wc2026_simulator.html` (o `http://TU-IP-LOCAL:8000/...` desde otro dispositivo en la misma red).

**Opción 3 — URL pública gratis (30 segundos, sin cuenta):**
1. Andá a **https://app.netlify.com/drop**
2. Arrastrá `wc2026_simulator.html` a la ventana.
3. Te da una URL pública tipo `https://nombre-random.netlify.app` que podés compartir.

(Alternativas equivalentes: Cloudflare Pages, GitHub Pages, Vercel. Cualquier hosting estático sirve porque es un solo HTML.)

## Qué hace

5 pestañas:
- **Título** — probabilidad de cada equipo por fase (R32 → campeón), bracket OFICIAL FIFA.
- **Partidos de hoy** — predicción de la fecha con cuota justa.
- **vs Casa** — probabilidad del modelo vs cuotas reales de-vig, con edge en pp.
- **Enfrentamiento** — cualquier par de equipos, con intervalo creíble 90% + marcadores probables.
- **Fuerzas** — ranking ataque/defensa.

Controles arriba: selector de **modelo** (PyMC calibrado / re-entrenado decay), Nº de torneos, y toggles (Poisson bivariada, ajuste forma, lesiones).

## Re-entrenar el modelo (backend)

`retrain.py` baja el histórico de resultados internacionales (incluye WC2026 en vivo), pondera por recencia (decaimiento temporal) y reajusta ataque/defensa por equipo:

```bash
pip install numpy scipy
python retrain.py 3 400        # half-life 3 años, 400 draws
```

Genera `POST.json`. Para meterlo al simulador hay que re-embeberlo en el HTML (decime y te dejo el build automatizado). Corre en < 1 segundo.

**Modelo:** Poisson ataque/defensa jerárquico, ajustado por IRLS con prior gaussiano (shrinkage), posterior aproximada por Laplace. El bracket de knockout usa la estructura oficial FIFA (matches 73–104 + asignación de terceros del Annex C).

## Límite honesto

El modelo no ve alineaciones ni lesiones de último minuto (más allá del toggle manual). Donde discrepa fuerte de las casas, la casa suele tener info que el modelo no. Usá el intervalo creíble como filtro: ancho = no apostar.
