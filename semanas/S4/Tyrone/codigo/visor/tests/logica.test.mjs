// node --test visor/tests/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  relojSim, numero, TARJETAS, valorTarjeta, formatoTarjeta, cambioVsBase, sesionesActivas,
  ocupacionSnapshot, Serie, Limitador, siguienteEspera, SeguimientoEspejos, peatonDe, posicionEspejo,
  recortarRastro, encuadre, estadisticaCuadros,
} from "../js/logica.js";

const tarjeta = (id) => TARJETAS.find((t) => t.id === id);

test("reloj hh:mm:ss", () => {
  assert.equal(relojSim(0), "00:00:00");
  assert.equal(relojSim(3725.9), "01:02:05");
  assert.equal(relojSim(null), "--:--:--");
});

test("formato de KPIs con coma decimal y unidades", () => {
  assert.equal(numero(2.5, 1), "2,5");
  assert.equal(numero(undefined), "—");
  assert.equal(formatoTarjeta(tarjeta("busqueda"), 212.4), "212 s");
  assert.equal(formatoTarjeta(tarjeta("ocupacion"), 0.8771), "87,7 %");
  assert.equal(formatoTarjeta(tarjeta("falsas"), 1.5), "1,5 /100");
  assert.equal(formatoTarjeta(tarjeta("sesiones"), 12), "12");
  assert.equal(formatoTarjeta(tarjeta("busqueda"), null), "—");
});

test("valor de tarjeta acepta los nombres del contrato y alternativos", () => {
  assert.equal(valorTarjeta(tarjeta("falsas"), { falsas_liberaciones_100: 3.5 }), 3.5);
  assert.equal(valorTarjeta(tarjeta("falsas"), { falsas_lib_100: 2 }), 2);
  assert.equal(valorTarjeta(tarjeta("falsas"), { otra: 2 }), null);
  assert.equal(valorTarjeta(tarjeta("busqueda"), { busqueda_media_s: NaN }), null);
});

test("−X % vs a ciegas", () => {
  const c = cambioVsBase(220, 355, true);
  assert.equal(c.texto, "−38 % vs a ciegas");
  assert.equal(c.mejor, true);
  assert.ok(Math.abs(c.pct - (-38.028)) < 0.01);
  assert.equal(cambioVsBase(400, 355, true).texto, "+13 % vs a ciegas");
  assert.equal(cambioVsBase(400, 355, true).mejor, false);
  assert.equal(cambioVsBase(355, 355).texto, "±0 % vs a ciegas");
  assert.equal(cambioVsBase(1, 0), null);
  assert.equal(cambioVsBase(null, 3), null);
});

test("estado derivado del snapshot", () => {
  const s = {
    vehiculos: [
      { id: "a", con_app: true, estado: "ESTACIONADO" }, { id: "b", con_app: true, estado: "A_PIE" },
      { id: "c", con_app: false, estado: "ESTACIONADO" }, { id: "d", con_app: true, estado: "GUIADO" },
    ],
    puestos: [{ ocupados: 3, capacidad: 4 }, { ocupados: 1, capacidad: 4 }],
  };
  assert.equal(sesionesActivas(s), 2);
  assert.equal(ocupacionSnapshot(s), 0.5);
  assert.equal(ocupacionSnapshot({ puestos: [] }), null);
});

test("serie de 10 min descarta lo viejo y se reinicia si t retrocede", () => {
  const s = new Serie(600);
  for (let t = 0; t <= 1200; t += 10) s.agregar(t, t);
  assert.equal(s.t[0], 600);
  s.agregar(5, 1);
  assert.deepEqual(s.t, [5]);
  s.agregar(6, NaN);
  assert.equal(s.t.length, 1);
});

test("limitador de redibujo a 2 Hz y solo con cambios", () => {
  const l = new Limitador(2);
  assert.equal(l.debe(0), false);
  l.marcar();
  assert.equal(l.debe(0), true);
  l.marcar();
  assert.equal(l.debe(300), false);
  assert.equal(l.debe(500), true);
  assert.equal(l.debe(1200), false); // sin cambios nuevos
});

test("espera exponencial 1, 2, 4… hasta 30", () => {
  const vistas = [];
  let e = 1;
  for (let i = 0; i < 7; i++) { vistas.push(e); e = siguienteEspera(e); }
  assert.deepEqual(vistas, [1, 2, 4, 8, 16, 30, 30]);
});

test("el resaltado espejo se retira 5 s después de salir de espejos", () => {
  const s = new SeguimientoEspejos(5);
  s.actualizar(["sim_1"], 100);
  assert.deepEqual(s.visibles(), ["sim_1"]);
  s.actualizar([], 101);
  assert.equal(s.retirando("sim_1"), true);
  assert.deepEqual(s.actualizar([], 105.9), []);
  assert.deepEqual(s.visibles(), ["sim_1"]);
  assert.deepEqual(s.actualizar([], 106), ["sim_1"]);
  assert.deepEqual(s.visibles(), []);
});

test("si vuelve a espejos antes de 5 s, no se retira; espejo_fin también lo retira", () => {
  const s = new SeguimientoEspejos(5);
  s.actualizar(["a"], 0);
  s.actualizar([], 1);
  s.actualizar(["a"], 3);
  assert.equal(s.retirando("a"), false);
  assert.deepEqual(s.actualizar(["a"], 20), []);
  s.agregar("b");
  s.fin("b", 30);
  assert.deepEqual(s.purgar(34), []);
  assert.deepEqual(s.purgar(35), ["b"]);
});

test("el halo pasa al peatón cuando el conductor se bajó", () => {
  assert.equal(peatonDe("sim_veh42"), "ped_veh42");
  const snap = { vehiculos: [{ id: "sim_1", lat: 1, lon: 2, estado: "GUIADO" }],
                 peatones: [{ id: "ped_veh42", lat: 3, lon: 4 }] };
  assert.equal(posicionEspejo("sim_1", snap).tipo, "vehiculo");
  assert.deepEqual(posicionEspejo("sim_veh42", snap), { tipo: "peaton", lat: 3, lon: 4, estado: "A_PIE" });
  assert.equal(posicionEspejo("sim_x", snap), null);
});

test("rastro de 60 s, encuadre y estadística de cuadros", () => {
  const r = [[0, 0, 10], [0, 0, 50], [0, 0, 100]];
  assert.equal(recortarRastro(r, 100, 60).length, 2);
  assert.deepEqual(encuadre([{ lat: -2, lon: -79 }, { lat: -3, lon: -78 }]), [[-3, -79], [-2, -78]]);
  assert.equal(encuadre([]), null);
  const e = estadisticaCuadros([1, 2, 3, 4, 100]);
  assert.equal(e.max, 100);
  assert.equal(e.media, 22);
});
