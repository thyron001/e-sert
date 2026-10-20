---
semana: S4
persona: Pablo
sesion: 2
titulo: Sección de IA final y preguntas probables del profesor
horas: 3-4
modulo: informe
depende: [S4-Pablo-1, S3-Pablo-3]
entrega: [informe/pablo.md, informe/figuras/pablo/, ia/figuras_informe.py, informe/anexos/preguntas_profesor.md]
evidencias: [s2_figuras-ia.png]
---
# S4 · Sesión 2 · Pablo 🟢: Sección de IA final y preguntas probables del profesor

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (la IA es **la parte evaluable**), tu borrador de S3
(`proyecto/informe/pablo.md`), `ia/MODEL_CARD.md` y `ia/modelos/rf_final.json` (sesión 1).
El borrador tiene cifras de `rf_v1`; ahora todas deben salir de `rf_final` y de la corrida
final de Tyrone. Plazo real: sábado 14, 23:59.

## Objetivo
Dejar la sección de IA terminada, con figuras regeneradas por script y cada número
trazable, y un banco de preguntas probables del profesor con respuestas cortas.

## Pasos
1. Crea `ia/figuras_informe.py`, que regenera desde los datos (sin reentrenar) todas las
   figuras de la sección en `informe/figuras/pablo/` con `dpi=300`, ejes en español y verde
   del equipo para RF:
   - conteo de ventanas por clase y fuente (GeoLife, SUMO, Cuenca);
   - distribución de velocidad por clase con la línea de 8 km/h del umbral;
   - importancia de características (permutación sobre Cuenca, no `feature_importances_`);
   - matrices de confusión RF frente a umbral en Cuenca;
   - F1 de `vehiculo` en tráfico lento, RF frente a umbral;
   - efecto del suavizado temporal sobre las falsas liberaciones (de S3-2);
   - falsas liberaciones por 100 sesiones por penetración (lee
     `kpis/resultados/final/resumen.csv` de `origin/tyrone/s4`; si aún no está, usa los de
     S3 con `# MOCK: actualizar con la corrida final` y deja un pedido).
2. Reescribe `informe/pablo.md` (2 000–3 000 palabras) según `GUIA_ESTILO.md`:
   - **Problema:** qué es una falsa liberación y por qué una regla de velocidad falla (auto
     en tráfico lento, peatón trotando, saltos de GPS).
   - **Datos:** GeoLife (ingesta, remuestreo a 1 Hz, cómo se derivó `quieto`), trazas de
     SUMO con ruido AR(1) calibrado, grabaciones de Cuenca (minutos y ventanas por clase y
     teléfono). Tabla resumen.
   - **Ventanas y características:** 30 s, paso 5 s; tabla con cada característica y su
     fórmula (velocidad media, p85, varianza, aceleración, rumbo, *stop rate*, etc.).
   - **Modelo:** Random Forest, hiperparámetros, por qué **GroupKFold por usuario** (evita
     filtrar el mismo trayecto en entrenamiento y prueba).
   - **Línea base** y **suavizado temporal**.
   - **Resultados:** Cuenca como prueba nunca vista; tráfico lento; latencia; impacto en las
     falsas liberaciones del sistema.
   - **Discusión, limitaciones y trabajo futuro** (acelerómetro con SHL).
   Cada cifra con `<!-- fuente: ia/modelos/rf_final.json:metricas.f1_macro -->` o similar.
3. Verifica la sección con un subagente independiente: "compara cada número de
   `informe/pablo.md` con su fuente declarada y lista discrepancias". Corrige hasta cero.
4. Escribe `informe/anexos/preguntas_profesor.md`, con al menos 30 preguntas agrupadas, cada
   una con respuesta de 3 a 5 líneas, la evidencia (archivo o figura) y quién responde en la
   exposición:
   - IA (Pablo): ¿por qué RF y no una LSTM?, ¿hay fuga de datos?, ¿cómo se derivó `quieto`?,
     ¿transfiere GeoLife a Cuenca?, ¿qué pasa si el teléfono queda dentro del auto?, ¿por qué
     no el acelerómetro?, ¿por qué 30 s?, ¿qué pasa en un semáforo largo?
   - Sistema (Freddy), escenario y KPIs (Tyrone), app y cobro (Miguel): al menos 4 por
     persona; márcalas como "a confirmar con <Nombre>" y déjalo como pedido.
5. **Evidencia** `evidencias/s2_figuras-ia.png`: lámina 2×3 con miniaturas de las figuras
   finales de la sección (para revisar de un vistazo que son coherentes).

## Dónde escribir
`semanas/S4/Pablo/codigo/informe/pablo.md`, `semanas/S4/Pablo/codigo/informe/figuras/pablo/`,
`semanas/S4/Pablo/codigo/informe/anexos/`, `semanas/S4/Pablo/codigo/ia/figuras_informe.py` y
`evidencias/`.

## Hecho cuando
- [ ] `python ia/figuras_informe.py` regenera todas las figuras de la sección.
- [ ] `informe/pablo.md` no cita ninguna cifra de `rf_v1` y no tiene `TODO`; cualquier `MOCK`
  restante está listado en la bitácora con su pedido.
- [ ] El verificador independiente reporta cero discrepancias entre cifras y fuentes.
- [ ] `preguntas_profesor.md` tiene al menos 30 preguntas con respuesta y responsable.
- [ ] Existe la evidencia `s2_figuras-ia.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 2, Pablo). En "Pedidos a
otros": @Tyrone, @Freddy y @Miguel, revisen y respondan sus preguntas del anexo en su propia
sección o en la bitácora antes del sábado 14 a las 18:00.
