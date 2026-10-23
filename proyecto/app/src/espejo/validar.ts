// Validadores en tiempo de ejecución de los mensajes del espejo (CONTRATO §6b).
// Sirven para el test del mock y para descartar mensajes malformados del WS real.

import { ESTADOS_SESION, type FinEspejo, type MensajeEspejo } from '@/src/api/tipos';

const MODOS = ['a_pie', 'quieto', 'vehiculo'];
const AVISOS = ['saldo_bajo', 'saldo_agotado', 'tiempo_maximo_cerca', 'tiempo_maximo_superado', 'sesiones_bloqueadas'];

type Objeto = Record<string, unknown>;
const esObjeto = (x: unknown): x is Objeto => typeof x === 'object' && x !== null && !Array.isArray(x);
const esNumero = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const esTexto = (x: unknown): x is string => typeof x === 'string';
const esISO = (x: unknown) => esTexto(x) && !Number.isNaN(Date.parse(x)) && /Z$|[+-]\d\d:\d\d$/.test(x);
const conCampos = (o: Objeto, campos: Record<string, (v: unknown) => boolean>) =>
  Object.entries(campos).every(([k, f]) => k in o && f(o[k]));
const nulo = (f: (v: unknown) => boolean) => (v: unknown) => v === null || f(v);
const esCoordenada = (c: unknown) => Array.isArray(c) && c.length === 2 && c.every(esNumero);

const esDestino = (x: unknown) => esObjeto(x) && conCampos(x, { nombre: esTexto, lat: esNumero, lon: esNumero });
const esPuesto = (x: unknown) =>
  esObjeto(x) && conCampos(x, { puesto_id: esTexto, lat: esNumero, lon: esNumero, distancia_m: esNumero });
const esSesion = (x: unknown) =>
  esObjeto(x) &&
  conCampos(x, { sesion_id: (v) => esTexto(v) && v.startsWith('ses_'), minutos: esNumero, costo_usd: esNumero, retenido_usd: esNumero });
const esBilletera = (x: unknown) => esObjeto(x) && conCampos(x, { saldo: esNumero, disponible: esNumero });
const esRecibo = (x: unknown) =>
  esObjeto(x) &&
  conCampos(x, {
    minutos_reales: esNumero,
    minutos_cobrados: esNumero,
    cobrado_usd: esNumero,
    tarjeta_sert_usd: esNumero,
    ahorro_usd: esNumero,
  });

/** Un mensaje `espejo` con todas las claves de 6b y cada valor del tipo correcto. */
export function esMensajeEspejo(x: unknown): x is MensajeEspejo {
  return (
    esObjeto(x) &&
    x.tipo === 'espejo' &&
    conCampos(x, {
      veh_id: (v) => esTexto(v) && v.startsWith('sim_'),
      t_sim: esNumero,
      ts: esISO,
      estado: nulo((v) => ESTADOS_SESION.includes(v as never)),
      lat: (v) => esNumero(v) && Math.abs(v) <= 90,
      lon: (v) => esNumero(v) && Math.abs(v) <= 180,
      modo: nulo((v) => MODOS.includes(v as string)),
      destino: nulo(esDestino),
      puesto: nulo(esPuesto),
      ruta: (v) => Array.isArray(v) && v.every(esCoordenada),
      sesion: nulo(esSesion),
      billetera: nulo(esBilletera),
      avisos: (v) => Array.isArray(v) && v.every((a) => AVISOS.includes(a as string)),
      recibo: nulo(esRecibo),
    })
  );
}

export function esFinEspejo(x: unknown): x is FinEspejo {
  return esObjeto(x) && x.tipo === 'espejo_fin' && esTexto(x.veh_id);
}
