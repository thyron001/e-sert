**Estado:** NO fusionado en main: falla 1 pytest (`informe/tests/test_informe.py::test_genera_pdf_sin_pandoc`, por la ruta fija `RAIZ_REPO = AQUI.parents[4]` de `construir_informe.py`, que solo es correcta dentro de `semanas/S4/Pablo/codigo/`). Todo queda en `unificacion/s4`, listo para fusionarse a mano. Tampoco habría tag `v1.0`: `verificar_informe.py` sale con 1 (30 marcadores `[PENDIENTE]`) y la suite e2e, la demo y SUMO no son verificables en este entorno.

# S4 · Resultado de la unificación final

La tarea programada se ejecutó el **domingo 2026-11-15** sin nadie presente. La rama de trabajo es
`unificacion/s4`, creada desde `origin/main` (`f87e818`). Antes de empezar no existía el tag `v1.0`.
`publicar_resultados.py --push` no hizo cambios, porque main ya tenía los resultados de las cuatro
ramas.

## Ramas por persona

El plazo era `2026-11-14T23:59:59-05:00`.

| Persona | Rama | Commits | Último commit | Tardía | Sesiones (estado.json) | Evidencias encontradas / declaradas | Criterios | PDF semanal | Sección del informe (`wc -w`) |
|---|---|---|---|---|---|---|---|---|---|
| Tyrone | `origin/tyrone/s4` (`12a9cfc`) | 3 | 2026-11-13T21:25:07-05:00 | no | S1 parcial · S2 hecha · S3 hecha | 9 / 9 | 17 / 18 | sí | `tyrone.md`: 2326 (2174 según el armado) |
| Freddy | `origin/freddy/s4` (`832d58b`) | 6 | 2026-11-14T09:05:25-05:00 | no | S1 parcial · S2 hecha · S3 hecha | 9 / 9 | 15 / 17 | sí | `freddy.md`: 2635 (2517 según el armado) |
| Pablo | `origin/pablo/s4` (`c69c836`) | 4 | 2026-11-13T12:12:05-05:00 | no | S1 hecha · S2 hecha · S3 parcial | 7 / 7 | 14 / 17 | sí | `pablo.md`: 2641 (2595 según el armado), 1 `[PENDIENTE]` |
| Miguel | `origin/miguel/s4` (`5f1542b`) | 8 | 2026-11-15T00:16:10-05:00 | **sí** (2 commits: `7bfa3a4` 00:06 y `5f1542b` 00:16 del domingo) | S1 parcial · S2 parcial · S3 parcial | 9 / 9 | 13 / 17 | sí | `miguel.md`: 2100 (2039 según el armado) |

- Ninguna rama quedó sin push. La única tardía es la de Miguel, y se incluyó igual.
- Las cifras de `wc -w` cuentan los comentarios `<!-- fuente -->`. El conteo del armado no los cuenta.
- **Tyrone:** S4-1 quedó parcial porque falta probar `demo.ps1` en Windows y el modo remoto con `ESERT_TOKEN_SIM`. `demo/plan_b/snapshots_demo.jsonl` se entregó comprimido como `.jsonl.gz` (13,7 MB), porque sin comprimir pesaba 136 MB.
- **Freddy:** S4-1 quedó parcial. Con SUMO, 2 fallos e2e en falsas liberaciones (faltaba `rf_v1.joblib`), y `pytest -m vps` necesita el token en el VPS.
- **Pablo:** S4-3 quedó parcial (3/6). Armó el informe sin las secciones de los demás y se quedó esperando el `resumen.csv` de Tyrone, que ya está en `proyecto/kpis/resultados/final/`.
- **Miguel:**
  - Las tres sesiones quedaron parciales:
    - no hubo iPhone físico;
    - el guion se salió de ±30 s;
    - las latencias quedaron sin CSV;
    - la entrega llegó tarde.
  - Falta `app/ensayo/latencias/`.

## Conflictos, archivos revertidos y archivos no copiados

- **Conflictos:** solo `bitacoras/freddy.md`, que se resolvió con la versión de main (ya traía las 3 entradas S4 de la rama). Los demás merges fueron limpios. No hubo conflictos no triviales.
- **Revertidos a `origin/main`** (están fuera de la carpeta S4 de la persona):
  - Freddy: `semanas/S2/Freddy/RESUMEN.md` y `semanas/S2/Freddy/estado.json`. Es su "Reverificación de S2" del 14-nov, que sube S2-3 de 4/7 a 6/7. Si Tyrone la acepta, puede traerla con `git checkout origin/freddy/s4 -- semanas/S2/Freddy/`.
  - Tyrone: 175 archivos nuevos en `semanas/S3/Tyrone/codigo/`, del commit S3-3 `91691cb`, que viajó dentro de `tyrone/s4`. Se descartaron solo los añadidos; el `codigo/` que ya tenía main se conserva. Ese código ya está en S4, en `proyecto/`.
- **Respetado:** `roadmap/templates/base.html` de Tyrone, que añade el enlace "Demo en vivo". Es planificación de Tyrone.
- **Cambios a la planificación descartados:** ninguno. Freddy, Pablo y Miguel no tocaron archivos de planificación ni sus `sesion-*.md`.
- **No copiados a `proyecto/`** (no pertenecen a los módulos de su dueño):
  - Tyrone: `informe/tyrone.cifras.json` y `informe/tyrone.plantilla.md`.
  - Freddy:
    - `comun/CONTRATO.propuesto.md` (sigue su propio flujo, ver más abajo);
    - `informe/freddy_cifras.py`;
    - `informe/datos/freddy/*.json` (5 archivos).
  - Las cuatro personas: `.gitkeep` de la raíz de `codigo/`.
- **Excluidos por regla (`.env*`):** `backend/.env.ejemplo` (Freddy), `app/.env.example`, `backend/asistente/.env.ejemplo` y `backend/pagos/.env.ejemplo` (Miguel). Son plantillas vacías; si ya existían en `proyecto/`, se conservan las de antes.
- **Copiados:** Tyrone 312, Freddy 217, Pablo 143 y Miguel 191 archivos versionados. Incluye `ia/modelos/rf_final.joblib`, de 48 020 756 B (menos de 50 MB).
- **Posibles eliminaciones** (están en `proyecto/` y ya no en la copia S4; no se borraron):
  - `kpis/.gitkeep`, `visor/estilos.css` y `visor/visor.js` (Tyrone);
  - `ia/tests/datos/referencia_s2.json` (Pablo);
  - `app/.gitkeep` (Miguel).

## Tests y verificaciones

En "Entorno limpio" se instaló solo lo que declaran los `requirements.txt`. En "Entorno completado" se añadieron además las dependencias que faltaban.

| Verificación | Resultado | Detalle |
|---|---|---|
| pytest `comun/` | **ok** | 169 passed |
| pytest `visor/` | **ok** | 11 passed, 1 skipped |
| pytest `backend/` | ok con entorno completado | Entorno limpio: error de colección (`anthropic`). Completado (`anthropic`, `python-dotenv`, `rapidfuzz`): 244 passed, 2 skipped, 17 deselected (e2e) |
| pytest `traci/` | ok con entorno completado | Entorno limpio: 5 errores de colección (`httpx`). Completado (`httpx`, `sqlalchemy`): 74 passed, 12 skipped, 21 deselected |
| pytest `ia/` | ok, con 3 no verificables | Entorno limpio: error de colección (`pydantic`, que se importa a través de `traci.estados`). Completado: 164 passed, 10 skipped, 3 errores en `test_evaluacion.py::TestParticion`, porque falta `ventanas_prueba_geolife.parquet`, un dato procesado que no está versionado |
| pytest `kpis/` | ok con entorno completado | Entorno limpio: error de colección (`scipy`). Completado (`scipy`, `statsmodels`, `tabulate`, `jinja2`): 23 passed, 6 skipped |
| pytest `informe/` | **falla** | 1 failed, 18 passed. `test_genera_pdf_sin_pandoc` falla porque `RAIZ_REPO = AQUI.parents[4]` busca `/herramientas/explicacion_pdf.py` fuera del repo. El módulo no tiene `requirements.txt` (usa `markdown` y `fpdf2`) |
| `requirements.txt` de `demo/` | falla | `-r ../../../../../proyecto/backend/requirements.txt` solo funciona desde `semanas/S4/Tyrone/codigo/demo/`. Se instaló a mano para seguir |
| SUMO `centro_base.sumocfg --end 60` | **no verificable** | No hay Docker ni el contenedor `van3twin` en este entorno |
| `pytest -m e2e` (backend y traci) | **no verificable** | Necesita SUMO |
| `demo/verificar_demo.py` | **no verificable** | Necesita SUMO |
| Hash del modelo | **ok** | El SHA-256 de `rf_final.joblib` (`1bdac0d7…fd013e2`) coincide con `rf_final.json` y con `kpis/resultados/final/manifiesto.json` (`sha256_iguales: true`) |
| Informe: `construir_informe.py --fuentes proyecto` | **parcial** | Con el comando oficial (`proyecto/informe/…`) sale con 0, pero solo genera HTML por el error de `RAIZ_REPO` (y no hay motor LaTeX para pandoc). El PDF se generó ejecutando el script idéntico de Pablo con `--carpeta proyecto/informe`: `proyecto/informe/salida/informe_e-sert.pdf` (8,9 MB, con las 4 secciones). Su carpeta no se modificó |
| Informe: `verificar_informe.py` | **falla** (exit 1) | 30 marcadores `[PENDIENTE]`: el resumen (3), `80_resultados_integrados.md` (tabla completa), `90_conclusiones.md`, `pablo.md:123` y 8 en `anexos/preguntas_profesor.md`. Son las cifras finales de Tyrone que Pablo no alcanzó a integrar. Además hay avisos de cifras con la misma ruta y distinta clave. Las 4 secciones están presentes |
| Higiene | **ok** | `git ls-files` no tiene `.env` reales, ni `*.mp4`/`*.mov`, ni archivos de más de 50 MB. La búsqueda de secretos no encontró valores reales (solo tokens falsos de test). Existen `proyecto/demo/README.md` y `proyecto/app/plan_b/ENLACE_VIDEO.md`, este con enlace de Drive |
| `comun/docs/verificar_contrato_api.py` | **falla** (exit 1) | `POST /api/v1/pagos/preparar` y `GET /api/v1/pagos/{client_transaction_id}` están en la app pero no en la tabla §4.3. Es el pedido de Miguel de S2-2, que sigue abierto |

**Criterios:**
- **"Las pruebas pasan": NO.** Falla 1 pytest de `informe/`, y en el entorno limpio fallan en colección backend, traci, ia y kpis.
- **"Todo pasa": NO.** Además de lo anterior, `verificar_informe.py` sale con 1.

## Contrato

Queda en **v1.3 final**, que aplica la propuesta editorial de Freddy (S4-2). La fila `GET /salud` de
§4.3 ahora lista `ts?`, y al final hay una sección "Cambios en v1.3". El cambio es compatible:
`X-Contrato-Version` y `Salud.contrato` siguen en `1`. Las rutas `/pagos/*` no se añadieron, porque
Freddy no las propuso.

## Pedidos cruzados al cierre del proyecto

**Sin resolver:**

- @Freddy, de Miguel (S2-2 y S3-3):
  - `/pagos/*` y `POST /asistente/interpretar` en el contrato;
  - `anthropic`, `python-dotenv` y `rapidfuzz` en los requirements del backend;
  - montar `backend.asistente.router`.
- @Freddy, de Miguel (S3-1): `httpx` y `sqlalchemy` en `traci/requirements.txt`. Lo confirma esta unificación.
- @Freddy, de Tyrone (S3-3 y S4-1): el `kpi` del WS sin `busqueda_media_s` ni `co2_busqueda_kg_h`.
- @Freddy, de Tyrone (S4-1 y S4-3): el mapa queda en 0 ocupados con `--publicar`/`correr_guiado`. Miguel reporta lo mismo: "0/610".
- @Freddy, de Tyrone (S3-1 y S4-2): `Guia._alcanzable` acepta puestos que están detrás del auto. Tyrone lo contiene con una guarda local en `correr_una.py`.
- @Freddy, de Pablo (S3-2 y S4-1): confirmar `REGRESANDO→A_PIE` para usar k=5.
- @Tyrone [VPS], de Freddy y Miguel (S4-1 y S4-2): configurar `ESERT_TOKEN_SIM` en Dokploy y redesplegar.
- @Tyrone, de Miguel (S4-3): copiar el video del plan B a la laptop y a un USB y comprobar su SHA-256.
- @Tyrone y @Pablo: integrar las cifras de `kpis/resultados/final/resumen.csv` en el resumen, la tabla integrada, las conclusiones, `pablo.md` y el anexo (los 30 `[PENDIENTE]`).
- @Pablo: corregir `RAIZ_REPO` en `informe/construir_informe.py` y añadir `informe/requirements.txt` (`markdown`, `fpdf2`, `pillow`).
- @Pablo: añadir a `ia/requirements.txt` la dependencia de `pydantic` que entra por `traci.estados`, y versionar o generar el parquet que usa `test_evaluacion.py`.
- @Tyrone: añadir a `kpis/requirements.txt` `scipy`, `statsmodels`, `tabulate` y `jinja2`, y corregir el `-r` relativo de `demo/requirements.txt`.
- @Freddy, @Tyrone y @Miguel, de Pablo (S4-2): confirmar las 15 preguntas del anexo.

**Resueltos o atendibles:**

- `rf_v1.joblib` ya no hace falta: `rf_final.joblib` está versionado en `proyecto/ia/modelos/` y su hash coincide.
- El `resumen.csv` de Tyrone y `demo/` ya existen en `proyecto/`.
- El video del plan B ya tiene enlace en `ENLACE_VIDEO.md`.

## Riesgos para la entrega y la exposición del lunes 16

- **`main` no tiene S4.** Si Tyrone acepta el estado actual, basta con
  `git switch main && git pull && git merge --no-ff origin/unificacion/s4 -m "[S4-U] Versión final de entrega" && git push`.
  - El arreglo mínimo del test es cambiar `AQUI.parents[4]` por una búsqueda del directorio que contiene `herramientas/`.
  - Después, `python proyecto/informe/construir_informe.py --fuentes proyecto` debería dar el PDF directamente.
- **El informe tiene 30 `[PENDIENTE]`** en el resumen, los resultados integrados y las conclusiones, que es lo primero que lee el profesor. Hay que reemplazarlos con `proyecto/kpis/resultados/final/resumen.csv` y volver a armarlo.
- **No se verificó aquí:**
  - SUMO con GUI;
  - la suite e2e;
  - `verificar_demo.py`;
  - `demo.ps1` en Windows;
  - el teléfono espejo contra el VPS, que necesita `ESERT_TOKEN_SIM` en Dokploy;
  - el modo `--local` en la LAN (plan B);
  - Payphone en modo de prueba.
- **Mapa en 0/610 durante la demo guiada:** el visor y la app pueden mostrar ocupación vacía y KPIs "—" (pedido abierto a Freddy).
- **Plan B:** el video solo está en Drive. Si no hay internet en el aula, no está disponible, salvo que se copie antes a la laptop o a un USB.
- **Secciones débiles:**
  - `freddy.md` y `pablo.md` pasan un poco de 2 500 palabras;
  - las 15 preguntas del anexo están sin confirmar;
  - el iPhone físico no se probó.

### Lista de comprobación para el lunes por la mañana
1. Fusionar `unificacion/s4` en `main` (con el arreglo de `RAIZ_REPO` si se quiere el test en verde) y poner el tag `v1.0` a mano.
2. Reemplazar los 30 `[PENDIENTE]` con las cifras de `resumen.csv` y volver a armar el informe hasta que `verificar_informe.py` salga con 0.
3. Arrancar `van3twin` y ejecutar `sumo -c proyecto/sumo/centro_base.sumocfg --end 60` y `python proyecto/demo/verificar_demo.py`.
4. Ejecutar `pytest -m e2e` en `proyecto/backend/` y `proyecto/traci/` con SUMO.
5. Poner `ESERT_TOKEN_SIM` en Dokploy, redesplegar el VPS y probar `/salud` y el visor en `demo.e-sert.tesisucuenca.com`.
6. Probar el teléfono espejo contra el VPS y, como plan B, en la LAN con `--local`.
7. Hacer una recarga de Payphone en modo de prueba de punta a punta.
8. Descargar el video del plan B a la laptop y a un USB, y comprobar el SHA-256 de `ENLACE_VIDEO.md`.
9. Ensayar `demo.ps1` en la laptop Windows de la exposición, con el proyector y el cronómetro.
10. Revisar que la ocupación del mapa no quede en 0/610 durante la demo guiada; si queda, ir directo al video.
