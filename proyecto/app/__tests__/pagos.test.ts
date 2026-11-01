import { afterEach, describe, expect, it, jest } from '@jest/globals';

import { consultarPago, esperarConfirmacion, leerMonto, prepararPago, type IntencionPago } from '@/src/api/pagos';
import { ErrorApi } from '@/src/api/tipos';
import { fechaLocal } from '@/src/ui/comunes';

const intencion = (estado: IntencionPago['estado']): IntencionPago => ({
  client_transaction_id: 'rec_1',
  usuario_id: 'app_x',
  monto: 5,
  estado,
  referencia_payphone: null,
  creada: '2026-10-27T15:00:00+00:00',
  actualizada: '2026-10-27T15:00:00+00:00',
});

describe('leerMonto (monto libre)', () => {
  it('acepta desde $5 con coma o punto y hasta 2 decimales', () => {
    expect(leerMonto('5')).toEqual({ monto: 5 });
    expect(leerMonto('7,50')).toEqual({ monto: 7.5 });
    expect(leerMonto('$12.25')).toEqual({ monto: 12.25 });
  });

  it('rechaza menos de $5, texto y más de 2 decimales', () => {
    expect(leerMonto('4.99')).toHaveProperty('error');
    expect(leerMonto('abc')).toHaveProperty('error');
    expect(leerMonto('5.001')).toHaveProperty('error');
    expect(leerMonto('2000')).toHaveProperty('error');
  });
});

describe('esperarConfirmacion (10 consultas cada 2 s)', () => {
  it('devuelve en cuanto deja de estar pendiente', async () => {
    const respuestas = [intencion('pendiente'), intencion('pendiente'), intencion('aprobado')];
    const consultar = jest.fn(async () => respuestas.shift()!);
    const r = await esperarConfirmacion(consultar, 10, 0);
    expect(r.estado).toBe('aprobado');
    expect(consultar).toHaveBeenCalledTimes(3);
  });

  it('se rinde tras los intentos y devuelve la última pendiente', async () => {
    const consultar = jest.fn(async () => intencion('pendiente'));
    const r = await esperarConfirmacion(consultar, 10, 0);
    expect(r.estado).toBe('pendiente');
    expect(consultar).toHaveBeenCalledTimes(10);
  });

  it('tolera fallos de red sueltos y lanza si nunca respondió', async () => {
    let n = 0;
    const r = await esperarConfirmacion(async () => {
      n += 1;
      if (n < 3) throw new ErrorApi(0, 'SIN_CONEXION', 'x');
      return intencion('rechazado');
    }, 10, 0);
    expect(r.estado).toBe('rechazado');
    await expect(
      esperarConfirmacion(async () => {
        throw new ErrorApi(0, 'SIN_CONEXION', 'x');
      }, 3, 0),
    ).rejects.toThrow(ErrorApi);
  });
});

describe('cliente de /pagos', () => {
  const fetchOriginal = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = fetchOriginal;
  });

  it('prepararPago envía usuario, monto y deep link a /api/v1/pagos/preparar', async () => {
    const llamadas: [string, RequestInit][] = [];
    globalThis.fetch = jest.fn(async (url: string, init: RequestInit) => {
      llamadas.push([url, init]);
      return new Response(JSON.stringify({ client_transaction_id: 'rec_1', payment_id: '1', pay_url: 'u', modo: 'mock' }), {
        status: 201,
      });
    }) as unknown as typeof fetch;
    const r = await prepararPago('http://192.168.3.168:8000', 'app_x', 10, 'exp://h/--/pagos/retorno');
    expect(r.modo).toBe('mock');
    expect(llamadas[0][0]).toBe('http://192.168.3.168:8000/api/v1/pagos/preparar');
    expect(JSON.parse(String(llamadas[0][1].body))).toEqual({
      usuario_id: 'app_x',
      monto: 10,
      url_app: 'exp://h/--/pagos/retorno',
    });
  });

  it('traduce RECARGA_MINIMA del backend a ErrorApi', async () => {
    globalThis.fetch = jest.fn(async () =>
      new Response(JSON.stringify({ error: { codigo: 'RECARGA_MINIMA', mensaje: 'La recarga mínima es $5.00.' } }), {
        status: 422,
      }),
    ) as unknown as typeof fetch;
    await expect(consultarPago('http://h/api/v1', 'rec_1')).rejects.toMatchObject({ codigo: 'RECARGA_MINIMA', estado: 422 });
  });
});

describe('fechaLocal', () => {
  it('formatea dd/mm hh:mm en la hora del teléfono', () => {
    const iso = new Date(2026, 9, 27, 9, 5).toISOString();
    expect(fechaLocal(iso)).toBe('27/10 09:05');
  });
});
