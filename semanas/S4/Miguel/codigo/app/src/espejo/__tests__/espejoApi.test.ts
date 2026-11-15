import { afterEach, describe, expect, jest, test } from '@jest/globals';

import { getCandidatos, origenServidor, urlSalud, urlWsEspejo } from '@/src/api/espejo';
import { ErrorApi } from '@/src/api/tipos';

const fetchOriginal = globalThis.fetch;

function respuestaFalsa(estado: number, cuerpo: unknown): Response {
  const texto = typeof cuerpo === 'string' ? cuerpo : JSON.stringify(cuerpo);
  return {
    ok: estado >= 200 && estado < 300,
    status: estado,
    statusText: `HTTP ${estado}`,
    text: async () => texto,
  } as unknown as Response;
}

function simularFetch(estado: number, cuerpo: unknown) {
  const f = jest.fn(async (_url: string | URL | Request, _init?: RequestInit) => respuestaFalsa(estado, cuerpo));
  globalThis.fetch = f as unknown as typeof fetch;
  return f;
}

afterEach(() => {
  globalThis.fetch = fetchOriginal;
});

describe('URLs del espejo', () => {
  test('https con /api/v1 → wss sin el prefijo', () => {
    expect(urlWsEspejo('https://demo.e-sert.tesisucuenca.com/api/v1', 'sim_veh42')).toBe(
      'wss://demo.e-sert.tesisucuenca.com/ws/espejo/sim_veh42',
    );
  });

  test('http con puerto → ws', () => {
    expect(urlWsEspejo('http://100.85.244.14:8001', 'sim_veh42')).toBe('ws://100.85.244.14:8001/ws/espejo/sim_veh42');
    expect(urlWsEspejo('http://100.85.244.14:8001/', 'sim_veh42')).toBe('ws://100.85.244.14:8001/ws/espejo/sim_veh42');
  });

  test('origenServidor y urlSalud', () => {
    expect(origenServidor('https://demo.e-sert.tesisucuenca.com/api/v1/')).toBe('https://demo.e-sert.tesisucuenca.com');
    expect(urlSalud('http://100.85.244.14:8001')).toBe('http://100.85.244.14:8001/api/v1/salud');
  });
});

describe('getCandidatos', () => {
  test('devuelve la lista y normaliza estado ausente a null', async () => {
    const f = simularFetch(200, [
      { id: 'sim_veh42', destino_nombre: 'Catedral', estado: 'GUIADO', t_sim: 30 },
      { id: 'sim_veh7', destino_nombre: 'Mercado', t_sim: 5 },
    ]);
    const lista = await getCandidatos('http://100.85.244.14:8001');
    expect(lista).toEqual([
      { id: 'sim_veh42', destino_nombre: 'Catedral', estado: 'GUIADO', t_sim: 30 },
      { id: 'sim_veh7', destino_nombre: 'Mercado', estado: null, t_sim: 5 },
    ]);
    expect(f.mock.calls[0][0]).toBe('http://100.85.244.14:8001/api/v1/espejo/candidatos');
  });

  test('un error HTTP con cuerpo de error se convierte en ErrorApi con su código', async () => {
    simularFetch(503, { error: { codigo: 'SIMULACION_DETENIDA', mensaje: 'No hay simulación' } });
    const e = await getCandidatos('http://x').catch((err: unknown) => err);
    expect(e).toBeInstanceOf(ErrorApi);
    expect(e).toMatchObject({ estado: 503, codigo: 'SIMULACION_DETENIDA', message: 'No hay simulación' });
  });

  test('un error HTTP sin cuerpo de error da HTTP_<estado>', async () => {
    simularFetch(500, 'falló');
    await expect(getCandidatos('http://x')).rejects.toMatchObject({ estado: 500, codigo: 'HTTP_500' });
  });

  test('una respuesta que no es lista da VALIDACION', async () => {
    simularFetch(200, { candidatos: [] });
    await expect(getCandidatos('http://x')).rejects.toMatchObject({ codigo: 'VALIDACION' });
  });

  test('fallo de red da SIN_CONEXION', async () => {
    globalThis.fetch = jest.fn(async () => {
      throw new TypeError('Network request failed');
    }) as unknown as typeof fetch;
    await expect(getCandidatos('http://x')).rejects.toMatchObject({ estado: 0, codigo: 'SIN_CONEXION' });
  });
});
