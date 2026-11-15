import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';

import { TIEMPO_ESPERA_MS, crearClienteHttp, getGuia, mensajeUsuario, raizApi } from '@/src/api/cliente';
import { ErrorApi } from '@/src/api/tipos';

type RespuestaFalsa = { ok: boolean; status: number; statusText: string; text: () => Promise<string> };

const fetchFalso = jest.fn<(url: string, init?: RequestInit) => Promise<RespuestaFalsa>>();
const fetchOriginal = globalThis.fetch;

function responder(status: number, cuerpo: unknown, statusText = '') {
  const texto = typeof cuerpo === 'string' ? cuerpo : JSON.stringify(cuerpo);
  fetchFalso.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText,
    text: async () => texto,
  });
}

/** Captura el rechazo para poder revisar sus campos. */
async function error(promesa: Promise<unknown>): Promise<ErrorApi> {
  try {
    await promesa;
  } catch (e) {
    return e as ErrorApi;
  }
  throw new Error('se esperaba un rechazo');
}

const BASE = 'http://h:8000';

beforeEach(() => {
  fetchFalso.mockReset();
  globalThis.fetch = fetchFalso as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = fetchOriginal;
});

describe('raizApi', () => {
  it.each([
    'http://h:8000',
    'http://h:8000/',
    'http://h:8000/api/v1',
    'http://h:8000/api/v1/',
    '  http://h:8000/api/v1//  ',
  ])('%p → http://h:8000/api/v1', (base) => {
    expect(raizApi(base)).toBe('http://h:8000/api/v1');
  });

  it('el tiempo de espera por defecto es 8 s', () => {
    expect(TIEMPO_ESPERA_MS).toBe(8000);
  });
});

describe('cliente HTTP', () => {
  it('getGuia arma la URL con la consulta y envía X-Contrato-Version', async () => {
    const guia = { puesto_id: 'pa_1', lat: -2.8975, lon: -79.0045, distancia_m: 120 };
    responder(200, guia);
    const api = crearClienteHttp(BASE);
    const r = await getGuia({ lat: -2.9, lon: -79.01, destino_lat: -2.897308, destino_lon: -79.004488 }, api);
    expect(r).toEqual(guia);
    expect(fetchFalso).toHaveBeenCalledTimes(1);
    const [url, init] = fetchFalso.mock.calls[0];
    expect(url).toBe(
      'http://h:8000/api/v1/guia?lat=-2.9&lon=-79.01&destino_lat=-2.897308&destino_lon=-79.004488',
    );
    expect(init?.method).toBe('GET');
    expect(init?.body).toBeUndefined();
    expect((init?.headers as Record<string, string>)['X-Contrato-Version']).toBe('1');
  });

  it('POST /sesiones envía el cuerpo en JSON', async () => {
    responder(201, { sesion_id: 'ses_1', estado: 'ESTACIONADO', retenido: 0.25 });
    const api = crearClienteHttp(`${BASE}/api/v1/`);
    const datos = { usuario_id: 'u1', placa: 'ABC-1234', puesto_id: 'pa_1' };
    const r = await api.crearSesion(datos);
    expect(r.retenido).toBe(0.25);
    const [url, init] = fetchFalso.mock.calls[0];
    expect(url).toBe('http://h:8000/api/v1/sesiones');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual(datos);
    expect((init?.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('cerrarSesion codifica el id en la URL', async () => {
    responder(200, { sesion_id: 'a/b c', minutos_reales: 12, minutos_cobrados: 15, debitado: 0.13, saldo: 4.87 });
    const api = crearClienteHttp(BASE);
    await api.cerrarSesion('a/b c', { ts: '2026-10-27T10:00:00-05:00', motivo: 'manual' });
    expect(fetchFalso.mock.calls[0][0]).toBe('http://h:8000/api/v1/sesiones/a%2Fb%20c/cerrar');
  });

  // Los 15 códigos de error del contrato (CONTRATO §4.2) con su HTTP.
  const CODIGOS: [string, number][] = [
    ['VALIDACION', 422],
    ['CONTRATO_INCOMPATIBLE', 400],
    ['TOKEN_SIM_INVALIDO', 401],
    ['SALDO_INSUFICIENTE', 402],
    ['SESIONES_BLOQUEADAS', 403],
    ['PUESTO_NO_EXISTE', 404],
    ['SESION_NO_EXISTE', 404],
    ['VEHICULO_NO_EXISTE', 404],
    ['SIN_PUESTOS_LIBRES', 404],
    ['PUESTO_LLENO', 409],
    ['SESION_ACTIVA', 409],
    ['SESION_YA_CERRADA', 409],
    ['TRANSICION_INVALIDA', 409],
    ['RECARGA_MINIMA', 422],
    ['ERROR_INTERNO', 500],
  ];

  it.each(CODIGOS)('%s (%p) → ErrorApi con mensaje para el usuario', async (codigo, estado) => {
    responder(estado, { error: { codigo, mensaje: `mensaje del servidor ${codigo}`, detalle: null } });
    const e = await error(crearClienteHttp(BASE).obtenerSesion('ses_1'));
    expect(e).toBeInstanceOf(ErrorApi);
    expect(e.estado).toBe(estado);
    expect(e.codigo).toBe(codigo);
    const texto = mensajeUsuario(e);
    expect(typeof texto).toBe('string');
    expect(texto.trim().length).toBeGreaterThan(0);
  });

  it('SALDO_INSUFICIENTE se muestra con el mensaje acordado', async () => {
    responder(402, { error: { codigo: 'SALDO_INSUFICIENTE', mensaje: 'x', detalle: null } });
    const e = await error(crearClienteHttp(BASE).crearSesion({ usuario_id: 'u', placa: 'ABC123', puesto_id: 'p' }));
    expect(mensajeUsuario(e)).toBe('Te falta saldo: recarga al menos $5 para buscar puesto.');
  });

  it('una respuesta que no es JSON da HTTP_<estado>', async () => {
    responder(502, '<html>Bad Gateway</html>', 'Bad Gateway');
    const e = await error(crearClienteHttp(BASE).listarPuestos());
    expect(e).toBeInstanceOf(ErrorApi);
    expect(e.estado).toBe(502);
    expect(e.codigo).toBe('HTTP_502');
    expect(mensajeUsuario(e).length).toBeGreaterThan(0);
  });

  it('si fetch falla (sin red) da SIN_CONEXION', async () => {
    fetchFalso.mockRejectedValueOnce(new TypeError('Network request failed'));
    const e = await error(crearClienteHttp(BASE).listarPuestos());
    expect(e.estado).toBe(0);
    expect(e.codigo).toBe('SIN_CONEXION');
    expect(mensajeUsuario(e)).toMatch(/conexión/);
  });

  it('si el servidor no responde a tiempo da TIEMPO_AGOTADO', async () => {
    // fetch que nunca responde y solo se rechaza cuando el cliente aborta.
    fetchFalso.mockImplementationOnce(
      (_url, init) =>
        new Promise((_resolver, rechazar) => {
          init?.signal?.addEventListener('abort', () => {
            const e = new Error('Aborted');
            e.name = 'AbortError';
            rechazar(e);
          });
        }),
    );
    const e = await error(crearClienteHttp(BASE, 50).listarPuestos());
    expect(e.codigo).toBe('TIEMPO_AGOTADO');
    expect(mensajeUsuario(e)).toMatch(/tardó demasiado/);
  });
});
