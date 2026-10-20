---
semana: S3
persona: Tyrone
sesion: 2
titulo: Análisis estadístico y figuras finales de KPIs
horas: 3-4
modulo: kpis
depende: [S3-Tyrone-1, S3-Freddy-1]
entrega: [kpis/analisis.py, kpis/figuras.py, kpis/figuras/, kpis/resultados/tabla_kpis.md, kpis/resultados/tabla_kpis.tex, kpis/resultados/hallazgos.md, kpis/tests/test_analisis.py]
evidencias: [s2_busqueda-vs-penetracion.png, s2_falsas-liberaciones.png]
---
# S3 · Sesión 2 · Tyrone 🔵: Análisis estadístico y figuras finales de KPIs

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (KPIs) y tu bitácora de S3-1. Parte de
`kpis/resultados/experimentos.csv` y de `kpis/resultados/vehiculos/*.csv.gz`. Si faltan
corridas, trabaja con las que haya y deja el código listo para regenerar todo con un comando.
Si los KPIs de Freddy siguen en mock (`NaN`), las figuras de sistema se generan igual con la
leyenda "pendiente". Estas figuras van **directas al informe y a la presentación**: deben ser
honestas, legibles y reproducibles.

## Objetivo
Convertir las 24 corridas en estadísticas con **intervalos de confianza del 95 %**,
comparaciones pareadas contra la búsqueda a ciegas y un juego de figuras y tablas finales.

## Pasos
1. Crea `kpis/analisis.py`:
   - `resumen(df, kpi)` por (penetración, clasificador): media, desviación, `n` e IC 95 % con
     t de Student entre semillas: `media ± t(0,975; n−1) · s/√n` con `scipy.stats.t.ppf`. Con
     `n = 3`, `t = 4,303`: los intervalos serán anchos y así se reportan.
   - Para KPIs por vehículo (tiempo y distancia de búsqueda), añade un IC complementario por
     *bootstrap* sobre vehículos agrupando semillas: `scipy.stats.bootstrap(..., n_resamples=10_000,
     method="BCa", random_state=0)`. La réplica independiente es la semilla; el *bootstrap* va solo
     en la tabla, rotulado como tal.
   - **Pareado por semilla** (números aleatorios comunes): `d_s = KPI(p, s) − KPI(0, s)`, IC 95 %
     de la media de `d` y mejora relativa `%`. Para umbral frente a rf a igual penetración,
     `scipy.stats.ttest_rel`. Si reportas varios valores p, corrige con Holm
     (`statsmodels.stats.multitest.multipletests(method="holm")`).
   - Maneja `NaN` (corridas fallidas o mock) sin romper: `n` real en cada celda.
2. Crea `kpis/figuras.py` (`python -m kpis.figuras` regenera todo en menos de 1 min):
   - estilo único: 6,4 × 4 in, fuente 10 pt, ejes con unidades, paleta fija en un `dict`
     (rf azul, umbral naranja, línea base gris discontinua con su banda IC), apta para daltónicos;
   - cada figura en `kpis/figuras/` como PNG (`dpi=150`) y PDF vectorial para el informe.
   - Figuras: **F1** tiempo de búsqueda medio vs penetración (barras de error IC 95 %);
     **F2** distancia de búsqueda; **F3** CO₂ de búsqueda (kg/h); **F4** falsas liberaciones por
     100 sesiones, umbral vs rf, barras agrupadas con IC; **F5** retardo de cierre (caja por
     sesión + media con IC); **F6** error de facturación de la app frente a la tarjeta SERT;
     **F7** precisión del mapa de ocupación vs penetración; **F8** CDF del tiempo de búsqueda por
     penetración.
3. Tablas `kpis/resultados/tabla_kpis.md` y `.tex` (`DataFrame.to_latex`, estilo *booktabs*):
   una fila por (penetración, clasificador), formato `media ± semiancho`, y una columna de mejora
   vs a ciegas con su IC.
4. Escribe `kpis/resultados/hallazgos.md`: de 5 a 8 frases con cifras e IC, por ejemplo "Con
   50 % de usuarios, el tiempo de búsqueda baja X % (IC 95 %: a–b %) frente a la búsqueda a
   ciegas". Si un IC cruza el cero, dilo: no hay mejora demostrada. Pablo lo cita en el informe.
5. **Tests** (`kpis/tests/test_analisis.py`):
   - `ic95([1, 2, 3])` da media 2 y semiancho `4,303/√3 ≈ 2,484`;
   - la diferencia pareada con datos sintéticos conocidos da el valor esperado;
   - `figuras.py` corre con un CSV sintético de 24 filas, también con columnas en `NaN`.
6. Paraleliza: un subagente escribe `figuras.py` y otro las tablas y los tests (archivos
   distintos); tú escribes `analisis.py`, que ambos importan (fija antes su interfaz).
7. Si faltan corridas de S3-1, relánzalas en segundo plano con el ejecutor (es reanudable) y
   vigílalas con `Monitor`; al terminar, regenera figuras.
8. **Evidencias:** copia F1 como `evidencias/s2_busqueda-vs-penetracion.png` y F4 como
   `evidencias/s2_falsas-liberaciones.png`.

## Dónde escribir
`semanas/S3/Tyrone/codigo/kpis/` y `evidencias/`.

## Hecho cuando
- [ ] Las 8 figuras existen en PNG y PDF, y cada punto lleva su IC 95 %.
- [ ] `tabla_kpis.md` y `tabla_kpis.tex` existen, con mejoras pareadas vs penetración 0.
- [ ] `hallazgos.md` tiene al menos 5 frases con cifras e IC.
- [ ] `pytest kpis/tests` pasa.
- [ ] `python -m kpis.figuras` regenera todo desde el CSV en menos de 1 min.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 2, Tyrone). En "Pedidos a otros":
@Pablo, las figuras F4 y F7 y `hallazgos.md` son para tu sección de IA; @Freddy, revisa que F5–F7
interpreten bien tus KPIs.
