# S1 · Freddy 🍅: resumen semanal

## Sesión 1 · 2026-10-22 · Contrato v1 y esquemas compartidos

Contrato v1 completo en `codigo/comun/CONTRATO.propuesto.md`, con "Cambios respecto a v0":
el cierre de los autos simulados lo pide el controlador TraCI con `POST /sesiones/{id}/cerrar`;
hay formato y lista de errores, header `X-Contrato-Version: 1`, la ruta nueva
`POST /sim/paso` y el mensaje WS `verdad`, solo para el visor. El contrato se volvió código
compartido: `esquemas.py` (Pydantic v2, 41 modelos y 9 enums), `esquemas.ts` (espejo
TypeScript), `tarifa.json` + `tarifa.py` y 29 ejemplos JSON más un CSV de trazas. Lo cubren
163 tests de pytest, entre ellos la paridad `.ts` ↔ `.py`.

![Diagrama de componentes del contrato v1](evidencias/s1_contrato-diagrama.png)

Explicación: [explicaciones/s1_explicacion.pdf](explicaciones/s1_explicacion.pdf)
