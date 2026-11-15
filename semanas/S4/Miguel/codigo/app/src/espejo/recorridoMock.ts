// MOCK: reemplazar por WS /ws/espejo (S2-3) cuando Freddy publique el backend del espejo.
// Genera un recorrido de ~60 s reales de un conductor simulado, de BUSCANDO a CERRADA con recibo,
// con mensajes que cumplen al pie de la letra el JSON de CONTRATO §6b. Sin dependencias nativas:
// lo usan la app, el test (jest) y `npm run generar-mock` (que escribe recorrido_mock.json).

import { costoMinutos, minutosCobrados, montoRetencion, redondearCentavos, tarjetaSertUsd, TARIFA } from '@/src/api/tarifa';
import type {
  Aviso,
  BilleteraEspejo,
  CandidatoEspejo,
  Coordenada,
  Destino,
  EstadoSesion,
  FinEspejo,
  MensajeEspejo,
  MensajeEspejoWS,
  Modo,
  PuestoEspejo,
  SesionEspejo,
} from '@/src/api/tipos';

/** Mensajes (1 por segundo real) de cada estado. Suman 59 + el espejo_fin = 60 s. */
export const FASES: readonly { estado: EstadoSesion; mensajes: number; minutosSim: number }[] = [
  { estado: 'BUSCANDO', mensajes: 5, minutosSim: 1 },
  { estado: 'GUIADO', mensajes: 12, minutosSim: 2 },
  { estado: 'ESTACIONADO', mensajes: 6, minutosSim: 3 },
  { estado: 'A_PIE', mensajes: 15, minutosSim: 35 },
  { estado: 'REGRESANDO', mensajes: 8, minutosSim: 6 },
  { estado: 'SALIENDO', mensajes: 6, minutosSim: 3 },
  { estado: 'CERRADA', mensajes: 7, minutosSim: 0.5 },
];

/** Minutos simulados de la sesión: de la llegada (ESTACIONADO) al cierre. 3 + 35 + 6 + 3 = 47. */
export const MINUTOS_SESION = 47;
export const SALDO_INICIAL_USD = 0.32; // poco saldo: tras la retención queda menos de 10 min
export const RECARGA_EN_A_PIE_USD = 5.0; // el conductor recarga mientras hace sus diligencias
const T_SIM_INICIAL = 1180;
const TS_BASE = Date.UTC(2026, 10, 5, 15, 0, 0);

interface Escenario {
  vehId: string;
  destino: Destino;
  puesto: { puesto_id: string; lat: number; lon: number }; // puestos reales de puestos.csv (Tyrone, S1-2)
  desde: Coordenada; // de dónde viene el auto
  tSimInicial: number;
}

const ESCENARIOS: Escenario[] = [
  {
    vehId: 'sim_veh42',
    destino: { nombre: 'Parque Calderón', lat: -2.8975, lon: -79.0045 },
    puesto: { puesto_id: 'pa_337277973#1_0', lat: -2.8979243, lon: -79.0045503 },
    desde: [-2.8935, -79.0085],
    tSimInicial: T_SIM_INICIAL,
  },
  {
    vehId: 'sim_veh17',
    destino: { nombre: 'Mercado 10 de Agosto', lat: -2.9005, lon: -79.006 },
    puesto: { puesto_id: 'pa_49222366#2_0', lat: -2.900795, lon: -79.0059221 },
    desde: [-2.8960, -79.0110],
    tSimInicial: 1415,
  },
  {
    vehId: 'sim_veh08',
    destino: { nombre: 'Plaza San Francisco', lat: -2.899, lon: -79.006 },
    puesto: { puesto_id: 'pa_42201285#3_0', lat: -2.8990384, lon: -79.0062565 },
    desde: [-2.9030, -79.0010],
    tSimInicial: 962,
  },
  {
    vehId: 'sim_veh63',
    destino: { nombre: 'Museo Pumapungo', lat: -2.907, lon: -78.996 },
    puesto: { puesto_id: 'pa_893253783_0', lat: -2.9046898, lon: -78.9970567 },
    desde: [-2.9000, -79.0020],
    tSimInicial: 2030,
  },
];

/** Candidatos de GET /espejo/candidatos (vehículos con app que aún no estacionan). */
export function candidatosMock(): CandidatoEspejo[] {
  return ESCENARIOS.map((e, i) => ({
    id: e.vehId,
    destino_nombre: e.destino.nombre,
    estado: i === 2 ? null : 'BUSCANDO', // uno todavía no empieza a buscar
    t_sim: e.tSimInicial,
  }));
}

function distanciaM(a: Coordenada, b: Coordenada): number {
  const R = 6371000;
  const rad = Math.PI / 180;
  const x = (b[1] - a[1]) * rad * Math.cos(((a[0] + b[0]) / 2) * rad);
  const y = (b[0] - a[0]) * rad;
  return Math.hypot(x, y) * R;
}

/** Interpola `n` puntos equiespaciados (en distancia) a lo largo de una polilínea. */
function muestrear(linea: Coordenada[], n: number): Coordenada[] {
  const tramos = linea.slice(1).map((p, i) => distanciaM(linea[i], p));
  const total = tramos.reduce((s, d) => s + d, 0);
  const puntos: Coordenada[] = [];
  for (let k = 0; k < n; k++) {
    let objetivo = (total * k) / Math.max(1, n - 1);
    let i = 0;
    while (i < tramos.length - 1 && objetivo > tramos[i]) {
      objetivo -= tramos[i];
      i++;
    }
    const f = tramos[i] === 0 ? 0 : Math.min(1, objetivo / tramos[i]);
    const [a, b] = [linea[i], linea[i + 1]];
    puntos.push([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]);
  }
  return puntos;
}

const redondear = (c: Coordenada): Coordenada => [Number(c[0].toFixed(7)), Number(c[1].toFixed(7))];

/** Recorrido completo (mensajes `espejo` + `espejo_fin`) de un vehículo; `ts` fijo y reproducible. */
export function generarRecorrido(vehId = 'sim_veh42'): MensajeEspejoWS[] {
  const esc = ESCENARIOS.find((e) => e.vehId === vehId) ?? { ...ESCENARIOS[0], vehId };
  const puestoC: Coordenada = [esc.puesto.lat, esc.puesto.lon];
  const destinoC: Coordenada = [esc.destino.lat, esc.destino.lon];

  // Trayecto del auto en "L" (como por la cuadrícula del Centro): desde → esquina → puesto.
  const esquina: Coordenada = [esc.desde[0], esc.puesto.lon];
  const trayecto = muestrear([esc.desde, esquina, puestoC], 17);
  const salida = muestrear([puestoC, [esc.puesto.lat, esc.puesto.lon + 0.004]], 14);
  const ida = muestrear([puestoC, destinoC], 5);
  const vuelta = muestrear([destinoC, puestoC], 8);

  const retencion = montoRetencion();
  // uuid4 fijo y reproducible: el primer grupo son los dígitos del vehículo en hexadecimal.
  const hexVeh = Number(vehId.replace(/\D/g, '') || 0).toString(16).padStart(8, '0').slice(-8);
  const sesionId = `ses_${hexVeh}-0000-4000-8000-000000000047`;
  const mensajes: MensajeEspejoWS[] = [];
  let tSim = esc.tSimInicial;
  let tLlegada = 0;
  let saldo = SALDO_INICIAL_USD;
  let i = 0;

  for (const fase of FASES) {
    const paso = (fase.minutosSim * 60) / fase.mensajes;
    for (let k = 0; k < fase.mensajes; k++, i++) {
      if (fase.estado === 'ESTACIONADO' && k === 0) tLlegada = tSim;
      if (fase.estado === 'A_PIE' && k === 0) saldo = redondearCentavos(saldo + RECARGA_EN_A_PIE_USD);

      let pos: Coordenada;
      let modo: Modo;
      let ruta: Coordenada[] = [];
      switch (fase.estado) {
        case 'BUSCANDO':
          pos = trayecto[k];
          modo = 'vehiculo';
          break;
        case 'GUIADO': {
          const j = 5 + k; // sigue por el mismo trayecto, ya con puesto asignado
          pos = trayecto[j];
          modo = 'vehiculo';
          ruta = trayecto.slice(j).map(redondear);
          break;
        }
        case 'ESTACIONADO':
          pos = puestoC;
          modo = 'quieto';
          break;
        case 'A_PIE':
          pos = ida[Math.min(k, ida.length - 1)];
          modo = k < ida.length - 1 ? 'a_pie' : 'quieto'; // camina y luego hace diligencias
          break;
        case 'REGRESANDO':
          pos = vuelta[k];
          modo = 'a_pie';
          break;
        case 'SALIENDO':
          pos = salida[k];
          modo = 'vehiculo';
          break;
        default: // CERRADA
          pos = salida[Math.min(6 + k, salida.length - 1)];
          modo = 'vehiculo';
      }

      const conSesion = tLlegada > 0;
      const cerrada = fase.estado === 'CERRADA';
      const minutos = conSesion ? (cerrada ? MINUTOS_SESION : (tSim - tLlegada) / 60) : 0;
      const cobrados = minutosCobrados(MINUTOS_SESION);
      const cobrado = costoMinutos(cobrados);

      let sesion: SesionEspejo | null = null;
      if (conSesion) {
        sesion = {
          sesion_id: sesionId,
          minutos: Number(minutos.toFixed(2)),
          costo_usd: cerrada ? cobrado : costoMinutos(minutos), // en curso, sin redondear a fracciones
          retenido_usd: cerrada ? 0 : retencion,
        };
      }
      const saldoMostrado = cerrada ? redondearCentavos(saldo - cobrado) : saldo;
      const retenido = conSesion && !cerrada ? retencion : 0;
      const billetera: BilleteraEspejo = {
        saldo: saldoMostrado,
        disponible: redondearCentavos(saldoMostrado - retenido),
      };

      // saldo_bajo: lo que queda tras cubrir lo comprometido (retención o costo en curso, el mayor)
      // alcanza para menos de aviso_saldo_min minutos.
      const comprometido = conSesion && !cerrada ? Math.max(retencion, sesion!.costo_usd) : 0;
      const avisos: Aviso[] = [];
      if (saldoMostrado - comprometido < costoMinutos(TARIFA.aviso_saldo_min)) avisos.push('saldo_bajo');

      const puesto: PuestoEspejo | null =
        fase.estado === 'BUSCANDO'
          ? null
          : { ...esc.puesto, distancia_m: Math.round(distanciaM(pos, puestoC)) };

      const mensaje: MensajeEspejo = {
        tipo: 'espejo',
        veh_id: vehId,
        t_sim: Number(tSim.toFixed(1)),
        ts: new Date(TS_BASE + i * 1000).toISOString(),
        estado: fase.estado,
        lat: Number(pos[0].toFixed(7)),
        lon: Number(pos[1].toFixed(7)),
        modo,
        destino: { ...esc.destino },
        puesto,
        ruta,
        sesion,
        billetera,
        avisos,
        recibo: cerrada
          ? {
              minutos_reales: MINUTOS_SESION,
              minutos_cobrados: cobrados,
              cobrado_usd: cobrado,
              tarjeta_sert_usd: tarjetaSertUsd(MINUTOS_SESION),
              ahorro_usd: redondearCentavos(tarjetaSertUsd(MINUTOS_SESION) - cobrado),
            }
          : null,
      };
      mensajes.push(mensaje);
      tSim += paso;
    }
  }

  const fin: FinEspejo = {
    tipo: 'espejo_fin',
    veh_id: vehId,
    t_sim: Number(tSim.toFixed(1)),
    ts: new Date(TS_BASE + i * 1000).toISOString(),
    motivo: 'salio_simulacion',
  };
  mensajes.push(fin);
  return mensajes;
}

/**
 * Reproduce el recorrido a 1 mensaje por segundo, con `ts` = hora real de emisión.
 * Misma firma que tendrá el cliente del WebSocket real: devuelve la función para desuscribirse.
 */
export function suscribirMock(
  vehId: string,
  onMensaje: (m: MensajeEspejoWS) => void,
  opciones: { intervaloMs?: number } = {},
): () => void {
  const mensajes = generarRecorrido(vehId);
  let i = 0;
  const emitir = () => {
    if (i >= mensajes.length) return detener();
    onMensaje({ ...mensajes[i++], ts: new Date().toISOString() });
  };
  const id = setInterval(emitir, opciones.intervaloMs ?? 1000);
  emitir();
  function detener() {
    clearInterval(id);
  }
  return detener;
}
