---
marp: true
theme: default
paginate: true
size: 16:9
lang: es
title: e-sert · parqueo inteligente en la zona SERT de Cuenca
style: |
  section { font-family: "DejaVu Sans", "Segoe UI", sans-serif; background: #ffffff; color: #1f2933; font-size: 26px; padding: 50px 64px; }
  h1 { color: #1E63D6; font-size: 44px; margin-bottom: 0.3em; }
  h2 { color: #1E63D6; font-size: 36px; border-bottom: 3px solid #1E63D6; padding-bottom: 6px; }
  strong { color: #0b2540; }
  footer { color: #6b7785; font-size: 15px; }
  section.titulo { background: linear-gradient(135deg, #f4f7fd 0%, #ffffff 60%); }
  section.titulo h1 { font-size: 56px; }
  .equipo { display: flex; gap: 18px; margin-top: 30px; font-size: 22px; }
  .equipo span { padding: 6px 14px; border-radius: 6px; color: #fff; }
  .t { background: #1E63D6; } .f { background: #FF7043; } .p { background: #2E9E4F; } .m { background: #C62828; }
  .cifras { display: flex; gap: 26px; margin-top: 18px; }
  .cifra { flex: 1; border-top: 6px solid #1E63D6; background: #f4f7fd; padding: 16px 18px; border-radius: 4px; }
  .cifra .n { font-size: 64px; font-weight: 700; color: #0b2540; line-height: 1.05; }
  .cifra .u { font-size: 20px; color: #3e4c59; }
  .cifra .ic { font-size: 18px; color: #52606d; margin-top: 8px; }
  .quien { position: absolute; top: 22px; right: 40px; font-size: 16px; padding: 3px 10px; border-radius: 4px; color: #fff; }
  .dos { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; align-items: center; }
  .nota { font-size: 18px; color: #52606d; }
  img[alt~="centro"] { display: block; margin: 0 auto; }
footer: "e-sert · Redes Vehiculares · Universidad de Cuenca · 16 nov 2026"
---

<!-- _class: titulo -->
<!-- _paginate: false -->

# e-sert: parqueo inteligente en la zona SERT de Cuenca

Simulación con SUMO + TraCI, clasificador de movimiento y app con cobro por tiempo real

<div class="equipo"><span class="t">Tyrone · escenario, experimentos, visor</span><span class="f">Freddy · TraCI y backend</span><span class="p">Pablo · IA</span><span class="m">Miguel · app</span></div>

---

## El problema: dar vueltas buscando parqueo

<span class="quien t">Tyrone</span>

- En el Centro Histórico de Cuenca el parqueo en la vía es **tarifado (SERT)** y escaso en hora pico.
- Quien busca no sabe qué puestos están libres: **circula a ciegas**, gasta tiempo y combustible y congestiona a los demás.
- La tarjeta SERT se paga **por bloques** de tiempo, se use o no el bloque completo.

**Pregunta:** si una parte de los conductores usa una app que sabe qué puestos se liberan, ¿cuánto baja la búsqueda para todos?

---

## Objetivo y alcance

<span class="quien t">Tyrone</span>

- **Mapa de ocupación en vivo** a partir del movimiento del teléfono: un clasificador detecta cuándo el conductor se baja (parquea) y cuándo vuelve a conducir (libera).
- **Guiado** de los usuarios de la app al puesto libre más cercano y **cobro por el tiempo real**.
- Medir el efecto con **penetración de la app** de 0, 20, 50 y 80 %.

<p class="nota"><strong>Todo es simulado:</strong> tráfico, conductores y GPS salen de SUMO; el teléfono solo <em>refleja</em> un auto simulado (modo espejo). No hay pruebas de campo.</p>

---

## Arquitectura

<span class="quien f">Freddy</span>

![h:470 centro](img/s1_contrato-diagrama.png)

<p class="nota">SUMO + controlador TraCI (contenedor) → backend FastAPI (sesiones, billetera, WebSocket) → visor web y app. Contrato v1.2.</p>

---

## Escenario SUMO: Centro Histórico

<span class="quien t">Tyrone</span>

<div class="dos">

![h:400](img/s1_red-centro.png)

![h:400](img/s2_puestos-sert.png)

</div>

<p class="nota">Red de OpenStreetMap, puestos SERT como <code>parkingArea</code>, demanda de hora pico calibrada a 85–95 % de ocupación; 75 min simulados (15 de <em>warm-up</em>) × 5 semillas.</p>

---

## Línea base: búsqueda a ciegas (0 %)

<span class="quien t">Tyrone</span>

<div class="cifras">
<div class="cifra"><div class="n">433 s</div><div class="u">tiempo medio de búsqueda</div><div class="ic">IC 95 % [418; 448] s</div></div>
<div class="cifra"><div class="n">1 456 m</div><div class="u">recorridos buscando</div><div class="ic">IC 95 % [1 407; 1 506] m</div></div>
<div class="cifra"><div class="n">838 g</div><div class="u">CO₂ de búsqueda por vehículo</div><div class="ic">IC 95 % [806; 871] g</div></div>
</div>

<p class="nota">4 646 vehículos que estacionan, 5 semillas; ocupación media 87,4 %. IC <em>bootstrap</em> jerárquico (semillas → vehículos, 10 000 remuestreos).</p>

---

## IA: ¿el conductor se bajó o sigue manejando?

<span class="quien p">Pablo</span>

![w:1000 centro](img/f04_matrices-confusion.png)

<p class="nota">Ventanas de GPS ruidoso → velocidad, aceleración, giros. Umbral de velocidad frente a <em>random forest</em> (<code>rf_final</code>, congelado). Una <strong>falsa liberación</strong> marca libre un puesto que sigue ocupado.</p>

---

## IA en la simulación: falsas liberaciones

<span class="quien p">Pablo</span>

![h:430 centro](../../informe/figuras/tyrone/f04_falsas_liberaciones.png)

<p class="nota">Corrida final, 5 semillas. Al 50 %: umbral 87,2 y <code>rf_final</code> 0,0 falsas liberaciones por 100 sesiones: el umbral confunde caminar despacio con volver a conducir.</p>

---

## App en modo espejo

<span class="quien m">Miguel</span>

<div class="dos">

![w:470](img/s3_espejo-recibo.png)

<div>

- El teléfono **sigue a un auto simulado** (`/ws/espejo`): ve su búsqueda, el puesto asignado y la sesión.
- Al volver al auto, la sesión se **cierra sola** y llega el **recibo** a la billetera.
- Recarga con Payphone en modo de pruebas.

</div>
</div>

---

## Cobro por tiempo real frente a tarjeta SERT

<span class="quien f">Freddy</span>

![h:430 centro](img/s2_cobro-sert-vs-real.png)

<p class="nota">La tarjeta cobra por bloques; e-sert cobra los minutos usados. Error de facturación medio al 50 % con <code>rf_final</code>: 0,018 USD por sesión.</p>

---

## Resultados al 50 % de penetración (`rf_final`)

<span class="quien t">Tyrone</span>

<div class="cifras">
<div class="cifra"><div class="n">+1,3 %</div><div class="u">tiempo de búsqueda vs a ciegas</div><div class="ic">438 s, IC 95 % [425; 451] s<br>a ciegas: 433 s</div></div>
<div class="cifra"><div class="n">+1,7 %</div><div class="u">CO₂ de búsqueda por vehículo</div><div class="ic">853 g, IC 95 % [825; 880] g<br>a ciegas: 838 g</div></div>
<div class="cifra"><div class="n">0,0</div><div class="u">falsas liberaciones por 100 sesiones</div><div class="ic">IC Wilson [0,0; 0,5]<br>umbral: 87,2 [85,6; 88,6]</div></div>
</div>

<p class="nota">Fuente: <code>kpis/resultados/final/resumen.csv</code> (5 semillas por escenario). Umbral y <code>rf_final</code> dan la misma búsqueda: el guiado usa el mapa del sistema, que solo ve a los usuarios con app.</p>

---

## Resultados frente a la penetración

<span class="quien t">Tyrone</span>

![h:450 centro](../../informe/figuras/tyrone/f01_kpis_vs_penetracion.png)

<p class="nota">Medias con IC 95 %: azul <code>rf_final</code>, tomate umbral, gris discontinuo la búsqueda a ciegas. El rombo oscuro es el <strong>oráculo</strong> al 50 % (guiado con la ocupación real): búsqueda −17,6 % frente a ciegas.</p>

---

## Demo en vivo

<span class="quien m">Miguel</span> 

- **sumo-gui:** el Centro Histórico con autos buscando parqueo.
- **Visor** (`demo.e-sert.tesisucuenca.com/visor`): puestos libres u ocupados, KPIs en vivo y el auto espejo resaltado.
- **Teléfono de Miguel** en modo espejo: búsqueda → puesto asignado → sesión → recibo.

<p class="nota">Un comando: <code>python demo/demo.py</code> (backend, controlador con sumo-gui y visor). Plan B: sin GUI → grabación → video.</p>

---

## Limitaciones

<span class="quien t">Tyrone</span>

- **Todo es simulado:** sin pruebas de campo ni GPS real; el ruido GPS es un modelo AR(1).
- La IA se entrenó con GeoLife (Pekín), no con trazas de Cuenca.
- Una sola franja (hora pico) y una red recortada al Centro Histórico.
- 5 semillas por escenario: los IC entre semillas son anchos.
- El cobro y la billetera usan Payphone en modo de pruebas.

---

## Conclusiones

<span class="quien t">Tyrone</span>

- **El clasificador funciona:** `rf_final` deja 0,0 falsas liberaciones por 100 sesiones al 50 % (umbral: 87,2), y el cobro por tiempo real queda correcto.
- **La búsqueda no baja con el mapa del sistema** (+1,3 % al 50 %): la app solo conoce a sus usuarios y la zona está al 87,4 % de ocupación.
- **Con ocupación real (oráculo) sí baja:** −17,6 % al 50 %. Falta una fuente de ocupación independiente de los usuarios (trabajo futuro).
- El sistema completo corre de punta a punta: SUMO → TraCI → backend → visor y app.

**Gracias. ¿Preguntas?**
