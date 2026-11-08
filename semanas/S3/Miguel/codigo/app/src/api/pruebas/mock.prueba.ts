// Prueba del mock fuera del teléfono: `npm run prueba:mock` (usa tsx).
// Revisa los 20 puestos, la tarifa (bloque mínimo, fracciones de 5 min) y el libro de la billetera.

import { crearClienteMock, generarPuestosFalsos } from '../mock';
import { minutosCobrados, montoRetencion } from '../tarifa';
import { ErrorApi } from '../tipos';

let fallos = 0;
function comprobar(condicion: boolean, descripcion: string) {
  console.log(`${condicion ? 'OK  ' : 'FALLA'} ${descripcion}`);
  if (!condicion) fallos++;
}

async function main() {
  const puestos = generarPuestosFalsos();
  comprobar(puestos.length === 20, '20 puestos falsos');
  comprobar(
    puestos.every((p) => Math.abs(p.lat + 2.8975) < 0.004 && Math.abs(p.lon + 79.0045) < 0.004),
    'todos a menos de ~400 m del Parque Calderón',
  );
  comprobar(puestos.every((p) => /^pa_.+_\d+$/.test(p.puesto_id)), 'puesto_id con formato pa_<edgeId>_<n>');
  const llenos = puestos.filter((p) => p.ocupados >= p.capacidad).length;
  comprobar(llenos > 0 && llenos < 20, `hay puestos libres y llenos (${20 - llenos} libres, ${llenos} llenos)`);

  comprobar(montoRetencion() === 0.25, 'retención = bloque de 30 min a $0.50/h = $0.25');
  comprobar(minutosCobrados(3) === 10, '3 min → cobro mínimo de 10 min');
  comprobar(minutosCobrados(10) === 10, '10 min → 10 min');
  comprobar(minutosCobrados(12) === 15, '12 min → 15 min (fracciones de 5)');
  comprobar(minutosCobrados(47.2) === 50, '47.2 min → 50 min');

  let reloj = new Date('2026-10-22T15:00:00Z');
  const api = crearClienteMock({ latenciaMs: 300, ahora: () => reloj });
  const usuario = 'app_prueba';

  const t0 = Date.now();
  const lista = await api.listarPuestos();
  const latencia = Date.now() - t0;
  comprobar(latencia >= 290, `latencia simulada ≈ 300 ms (medida ${latencia} ms)`);
  lista[0].ocupados = 999;
  comprobar((await api.listarPuestos())[0].ocupados !== 999, 'devuelve copias, no el estado interno');

  const b0 = await api.obtenerBilletera(usuario);
  comprobar(b0.saldo === 5 && b0.retenido === 0 && b0.disponible === 5, 'billetera inicial: $5 de saldo');

  const libre = puestos.find((p) => p.ocupados < p.capacidad)!;
  const lleno = puestos.find((p) => p.ocupados >= p.capacidad)!;
  try {
    await api.crearSesion({ usuario_id: usuario, placa: 'abc-1', puesto_id: lleno.puesto_id });
    comprobar(false, 'puesto lleno rechazado');
  } catch (e) {
    comprobar(e instanceof ErrorApi && e.codigo === 'PUESTO_LLENO' && e.estado === 409, 'puesto lleno rechazado (409 PUESTO_LLENO)');
  }

  const creada = await api.crearSesion({ usuario_id: usuario, placa: 'abc-1', puesto_id: libre.puesto_id });
  comprobar(creada.estado === 'ESTACIONADO' && creada.retenido === 0.25, 'sesión creada en ESTACIONADO con $0.25 retenidos');
  comprobar(/^ses_[0-9a-f-]{36}$/.test(creada.sesion_id), 'sesion_id con formato ses_<uuid4>');
  const b1 = await api.obtenerBilletera(usuario);
  comprobar(b1.saldo === 5 && b1.retenido === 0.25 && b1.disponible === 4.75, 'retención: saldo 5, retenido 0.25, disponible 4.75');
  const ocupadoTras = (await api.listarPuestos()).find((p) => p.puesto_id === libre.puesto_id)!.ocupados;
  comprobar(ocupadoTras === libre.ocupados + 1, 'el puesto suma un ocupado');

  reloj = new Date('2026-10-22T15:47:12Z'); // 47.2 min después
  const cerrada = await api.cerrarSesion(creada.sesion_id, { ts: reloj.toISOString(), motivo: 'manual' });
  comprobar(cerrada.minutos_cobrados === 50 && cerrada.debitado === 0.42, `cierre: 50 min, $0.42 (obtuvo ${cerrada.minutos_cobrados} min, $${cerrada.debitado})`);
  const b2 = await api.obtenerBilletera(usuario);
  comprobar(b2.saldo === 4.58 && b2.retenido === 0 && b2.disponible === 4.58, 'tras cerrar: saldo 4.58 y retención liberada');
  comprobar(
    b2.movimientos.map((m) => m.tipo).join(',') === 'recarga,retencion,debito,liberacion',
    'libro: recarga, retención, débito, liberación',
  );
  comprobar((await api.obtenerSesion(creada.sesion_id)).estado === 'CERRADA', 'GET /sesiones/{id} → CERRADA');

  try {
    await api.recargar(usuario, { monto: 2 });
    comprobar(false, 'recarga menor a $5 rechazada');
  } catch (e) {
    comprobar(e instanceof ErrorApi && e.codigo === 'RECARGA_MINIMA', 'recarga menor a $5 rechazada (RECARGA_MINIMA)');
  }
  const rec = await api.recargar(usuario, { monto: 5 });
  comprobar(rec.saldo === 9.58 && rec.movimiento_id.startsWith('mov_'), 'recarga de $5 → saldo 9.58');

  const guia = await api.pedirGuia({ lat: -2.9, lon: -79.0, destino_lat: -2.8975, destino_lon: -79.0045 });
  comprobar(puestos.some((p) => p.puesto_id === guia.puesto_id), `guía devuelve un puesto libre (${guia?.puesto_id}, ${guia?.distancia_m} m)`);

  console.log(fallos === 0 ? '\nTodo OK' : `\n${fallos} comprobaciones fallaron`);
  if (fallos > 0) throw new Error('prueba del mock fallida');
}

main();
