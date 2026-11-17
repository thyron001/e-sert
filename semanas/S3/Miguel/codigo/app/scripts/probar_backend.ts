// Recorre el flujo buscar → guiar → confirmar → activa → cerrar con el cliente HTTP real.
// Uso: npm run probar-backend -- http://192.168.1.20:8000/api/v1
// Sale con código 1 si algún paso no responde lo que dice el contrato.

import { cerrarSesion, crearClienteHttp, crearSesion, getBilletera, getGuia, getSesion, mensajeUsuario } from '@/src/api/cliente';
import { ErrorApi } from '@/src/api/tipos';
import { DESTINOS } from '@/src/datos/destinos';
import { PARTIDA_POR_DEFECTO } from '@/src/sesion/geo';

const url = process.argv[2] ?? process.env.EXPO_PUBLIC_API_URL ?? 'http://127.0.0.1:8000/api/v1';
const api = crearClienteHttp(url);
const usuario = `app_${crypto.randomUUID()}`; // crypto global de Node 20
let fallos = 0;
const comprobar = (ok: boolean, texto: string) => {
  console.log(`${ok ? 'OK  ' : 'FALLA'} ${texto}`);
  if (!ok) fallos++;
};

async function main() {
  console.log(`Backend: ${url}\nUsuario: ${usuario}\n`);
  const b0 = await getBilletera(usuario, api);
  comprobar(b0.saldo === 0 && b0.bloqueada === false, `billetera nueva en $0 (disponible ${b0.disponible})`);

  const destino = DESTINOS[0];
  const consulta = { lat: PARTIDA_POR_DEFECTO.lat, lon: PARTIDA_POR_DEFECTO.lon, destino_lat: destino.lat, destino_lon: destino.lon };
  const guia = await getGuia(consulta, api);
  comprobar(guia.puesto_id.startsWith('pa_'), `guía hacia ${destino.nombre}: ${guia.puesto_id} a ${guia.distancia_m} m del destino`);

  try {
    await crearSesion({ usuario_id: usuario, placa: 'ABC-1234', puesto_id: guia.puesto_id }, api);
    comprobar(false, 'sin saldo, POST /sesiones debía fallar');
  } catch (e) {
    comprobar(e instanceof ErrorApi && e.codigo === 'SALDO_INSUFICIENTE' && e.estado === 402, `sin saldo → ${(e as ErrorApi).codigo}: "${mensajeUsuario(e)}"`);
  }

  const rec = await api.recargar(usuario, { monto: 5 });
  comprobar(rec.saldo === 5, `recarga de prueba → saldo ${rec.saldo}`);

  const inicio = new Date(Date.now() - 12 * 60_000).toISOString(); // sesión de 12 min
  const creada = await crearSesion({ usuario_id: usuario, placa: 'ABC-1234', puesto_id: guia.puesto_id, ts: inicio }, api);
  comprobar(creada.estado === 'ESTACIONADO' && creada.retenido === 0.25, `sesión ${creada.sesion_id} ESTACIONADO, retenido ${creada.retenido}`);

  try {
    await crearSesion({ usuario_id: usuario, placa: 'ABC-1234', puesto_id: guia.puesto_id }, api);
    comprobar(false, 'segunda sesión debía fallar');
  } catch (e) {
    comprobar((e as ErrorApi).codigo === 'SESION_ACTIVA', `segunda sesión → ${(e as ErrorApi).codigo}`);
  }

  const s = await getSesion(creada.sesion_id, api);
  comprobar(s.estado === 'ESTACIONADO' && s.debitado == null, `GET /sesiones: ${s.estado}, inicio ${s.inicio}`);
  const b1 = await getBilletera(usuario, api);
  comprobar(b1.retenido === 0.25 && b1.disponible === 4.75, `billetera con retención: saldo ${b1.saldo}, disponible ${b1.disponible}`);

  const c = await cerrarSesion(creada.sesion_id, { ts: new Date().toISOString(), motivo: 'manual' }, api);
  comprobar(c.minutos_cobrados === 15 && c.debitado === 0.13 && c.saldo === 4.87, `cierre manual: ${c.minutos_reales} min reales → ${c.minutos_cobrados} cobrados, $${c.debitado}, saldo ${c.saldo}`);

  try {
    await cerrarSesion(creada.sesion_id, { ts: new Date().toISOString(), motivo: 'manual' }, api);
    comprobar(false, 'cerrar dos veces debía fallar');
  } catch (e) {
    comprobar((e as ErrorApi).codigo === 'SESION_YA_CERRADA', `cerrar otra vez → ${(e as ErrorApi).codigo}`);
  }

  console.log(fallos === 0 ? '\nTodo OK contra el backend real' : `\n${fallos} comprobaciones fallaron`);
  process.exit(fallos === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error(`Error: ${mensajeUsuario(e)} (${(e as Error).message})`);
  process.exit(1);
});
