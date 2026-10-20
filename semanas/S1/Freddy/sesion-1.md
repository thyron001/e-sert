---
semana: S1
persona: Freddy
sesion: 1
titulo: Contrato v1 y esquemas compartidos
horas: 3-4
modulo: comun
depende: []
entrega: [comun/esquemas.py, comun/esquemas.ts, comun/tarifa.json, comun/ejemplos/, comun/CONTRATO.propuesto.md]
evidencias: [s1_contrato-diagrama.png]
---
# S1 · Sesión 1 · Freddy 🍅: Contrato v1 y esquemas compartidos

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` y, con mucho cuidado, `docs/CONTRATO.md` (borrador v0).
Eres el **custodio del contrato**: es lo que permite que cuatro personas trabajen por separado
y que el domingo todo encaje. Un error aquí cuesta caro en S2 y S3.

## Objetivo
Revisar el contrato v0, cerrar sus huecos y convertirlo en **código compartido**: modelos
Pydantic para Python (TraCI, backend e IA), tipos TypeScript para la app, ejemplos JSON
válidos y tests que garanticen que todo es coherente.

## Pasos
1. Revisa `docs/CONTRATO.md` con ojo crítico y anota los huecos en
   `comun/CONTRATO.propuesto.md`. Este será el texto v1 completo: lo copia a `docs/` la
   unificación. Como mínimo decide:
   - ¿Cómo sabe el backend que un vehículo simulado salió del puesto, si `CERRADA` lo decide
     la máquina de estados? Respuesta: el controlador TraCI llama a `POST /sesiones/{id}/cerrar`.
   - Errores HTTP: formato `{"error": {"codigo": "...", "mensaje": "..."}}` y la lista de
     códigos (`SALDO_INSUFICIENTE`, `PUESTO_LLENO`, `SESION_NO_EXISTE`, `SESIONES_BLOQUEADAS`…).
   - Versionado: header `X-Contrato-Version: 1`.
   - Quién publica la ocupación real de SUMO para el KPI de precisión del mapa: un mensaje WS
     `{"tipo": "verdad"}`, solo en simulación y nunca visible para la app.
2. Crea `comun/esquemas.py` con Pydantic v2: todos los cuerpos de la sección 4, `PuntoGPS`,
   `ResultadoModo`, los mensajes WS (unión discriminada por `tipo`), la fila del CSV de trazas
   y los enums `Modo` y `EstadoSesion`. Usa docstrings en español.
3. Crea `comun/esquemas.ts` con los tipos TypeScript equivalentes, escritos a mano y con los
   mismos nombres de campos. Añade un comentario que indique que se sincronizan con
   `esquemas.py`.
4. Crea `comun/tarifa.json` con los valores del contrato y `comun/tarifa.py` con una función
   para cargarlo y validarlo.
5. Crea `comun/ejemplos/` con un JSON válido por cada mensaje: `ubicacion.json`, `modo.json`,
   `sesion_crear.json`, `snapshot_ws.json`, `kpi_ws.json`, etc.
6. Crea `comun/tests/test_esquemas.py` con pytest:
   - cada ejemplo valida contra su modelo;
   - un ejemplo malo (modo inventado o latitud fuera de rango) falla;
   - los nombres de campo del `.ts` coinciden con los del `.py`. Hazlo con un *parser*
     simple por expresiones regulares de `interface X { campo: ... }`.
7. **Evidencia** `evidencias/s1_contrato-diagrama.png`: un diagrama de componentes
   (SUMO+TraCI, backend, IA, app y visor) con flechas etiquetadas con los mensajes del
   contrato. Hazlo con matplotlib (cajas y flechas) o con graphviz si está instalado.

## Dónde escribir
`semanas/S1/Freddy/codigo/comun/` y `semanas/S1/Freddy/evidencias/`. **No** edites
`docs/CONTRATO.md` directamente.

## Hecho cuando
- [ ] `pytest comun/tests` pasa completo.
- [ ] `CONTRATO.propuesto.md` está completo y autocontenido (no "ver v0"), con una sección
  "Cambios respecto a v0".
- [ ] Hay un ejemplo JSON para cada mensaje, y `esquemas.ts` refleja `esquemas.py`.
- [ ] Existe la evidencia `s1_contrato-diagrama.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 1, Freddy). En "Pedidos a
otros", resume en 5 viñetas los cambios del contrato que afectan a cada persona.
