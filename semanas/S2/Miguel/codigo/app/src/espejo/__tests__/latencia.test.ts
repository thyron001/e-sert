import { describe, expect, test } from '@jest/globals';

import { RegistroLatencia, estimarDesfase, percentil } from '../latencia';

describe('percentil (rango más cercano)', () => {
  test('p50 y p95 de arreglos conocidos', () => {
    const uno_a_cien = Array.from({ length: 100 }, (_, i) => i + 1);
    expect(percentil(uno_a_cien, 50)).toBe(50);
    expect(percentil(uno_a_cien, 95)).toBe(95);
    expect(percentil([5, 1, 4, 2, 3], 50)).toBe(3); // no depende del orden de entrada
    expect(percentil([5, 1, 4, 2, 3], 95)).toBe(5);
    expect(percentil([7], 95)).toBe(7);
    expect(percentil([10, 20], 0)).toBe(10);
  });

  test('vacío → NaN', () => {
    expect(percentil([], 50)).toBeNaN();
  });

  test('no modifica el arreglo original', () => {
    const v = [3, 1, 2];
    percentil(v, 50);
    expect(v).toEqual([3, 1, 2]);
  });
});

describe('RegistroLatencia', () => {
  const ts = '2026-11-01T12:00:00.000Z';
  const base = Date.parse(ts);

  test('registrar calcula lat_total y lat_cliente', () => {
    const r = new RegistroLatencia();
    r.desfaseMs = 40; // el teléfono va 40 ms adelantado
    const m = r.registrar({ t_sim: 10, ts, recibidoEn: base + 150, pintadoEn: base + 190 });
    expect(m).toEqual({ t_sim: 10, lat_total_ms: 190 - 40, lat_cliente_ms: 40 });
    expect(r.muestras).toHaveLength(1);
  });

  test('resumen() y aCSV()', () => {
    const r = new RegistroLatencia();
    [100, 200, 300, 400].forEach((lat, i) =>
      r.registrar({ t_sim: i + 1, ts, recibidoEn: base + lat - 10 * (i + 1), pintadoEn: base + lat }),
    );
    expect(r.resumen()).toEqual({ n: 4, total_p50: 200, total_p95: 400, cliente_p50: 20, cliente_p95: 40 });
    expect(r.aCSV('local')).toBe(
      'modo,t_sim,lat_total_ms,lat_cliente_ms\nlocal,1,100,10\nlocal,2,200,20\nlocal,3,300,30\nlocal,4,400,40\n',
    );
    r.vaciar();
    expect(r.aCSV('vps')).toBe('modo,t_sim,lat_total_ms,lat_cliente_ms\n');
    expect(r.resumen().n).toBe(0);
  });
});

type Respuesta = { json(): Promise<unknown>; headers: { get(n: string): string | null } };

/** Reloj falso: cada llamada devuelve el siguiente valor de la lista. */
const relojDe = (valores: number[]) => {
  let i = 0;
  return () => valores[i++];
};

describe('estimarDesfase (Cristian)', () => {
  test('con ts en el cuerpo elige la muestra de menor RTT', async () => {
    const servidor = Date.parse('2026-11-01T12:00:00.000Z');
    // Tres muestras: RTT 300, 80 y 200 ms. El servidor responde con su hora en cada una.
    const tiemposServidor = [servidor, servidor + 1000, servidor + 2000];
    const t = [
      [servidor + 500, servidor + 800], // rtt 300
      [servidor + 1460, servidor + 1540], // rtt 80
      [servidor + 2400, servidor + 2600], // rtt 200
    ];
    let k = 0;
    const pedir = async (): Promise<Respuesta> => {
      const s = tiemposServidor[k++];
      return { json: async () => ({ estado: 'ok', ts: new Date(s).toISOString() }), headers: { get: () => null } };
    };
    const d = await estimarDesfase('http://x/api/v1/salud', 3, pedir, relojDe(t.flat()));
    expect(d.fuente).toBe('ts');
    expect(d.rttMs).toBe(80);
    // desfase = t1 − (servidor + rtt/2) = 1540 − (1000 + 40) = 500
    expect(d.desfaseMs).toBe(500);
  });

  test('sin ts usa el header Date (+500 ms) y reporta fuente date', async () => {
    const fecha = 'Sun, 01 Nov 2026 12:00:00 GMT';
    const servidor = Date.parse(fecha);
    const pedir = async (): Promise<Respuesta> => ({
      json: async () => ({ estado: 'ok' }),
      headers: { get: (n: string) => (n.toLowerCase() === 'date' ? fecha : null) },
    });
    const d = await estimarDesfase('http://x/api/v1/salud', 1, pedir, relojDe([servidor + 2000, servidor + 2100]));
    expect(d.fuente).toBe('date');
    expect(d.rttMs).toBe(100);
    // 2100 − (500 + 50) = 1550
    expect(d.desfaseMs).toBe(1550);
  });

  test('cuerpo no JSON también cae al header Date', async () => {
    const fecha = 'Sun, 01 Nov 2026 12:00:00 GMT';
    const servidor = Date.parse(fecha);
    const pedir = async (): Promise<Respuesta> => ({
      json: async () => {
        throw new SyntaxError('no json');
      },
      headers: { get: () => fecha },
    });
    const d = await estimarDesfase('u', 1, pedir, relojDe([servidor, servidor]));
    expect(d).toEqual({ desfaseMs: -500, rttMs: 0, fuente: 'date' });
  });

  test('sin ts ni Date lanza un error', async () => {
    const pedir = async (): Promise<Respuesta> => ({ json: async () => ({}), headers: { get: () => null } });
    await expect(estimarDesfase('u', 2, pedir, relojDe([0, 1, 2, 3]))).rejects.toThrow('desfase');
  });
});
