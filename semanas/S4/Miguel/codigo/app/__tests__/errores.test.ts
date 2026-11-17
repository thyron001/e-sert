import { describe, expect, jest, test } from '@jest/globals';

import { ErrorApi } from '@/src/api/tipos';
import { describirError, ERRORES } from '@/src/errores';

// Todos los códigos de CONTRATO §4.2 (CodigoError en comun/esquemas.ts) más los dos del cliente.
const CODIGOS = [
  'VALIDACION', 'CONTRATO_INCOMPATIBLE', 'TOKEN_SIM_INVALIDO', 'SALDO_INSUFICIENTE', 'SESIONES_BLOQUEADAS',
  'PUESTO_NO_EXISTE', 'SESION_NO_EXISTE', 'VEHICULO_NO_EXISTE', 'SIN_PUESTOS_LIBRES', 'PUESTO_LLENO',
  'SESION_ACTIVA', 'SESION_YA_CERRADA', 'TRANSICION_INVALIDA', 'RECARGA_MINIMA', 'ERROR_INTERNO',
  'SIN_CONEXION', 'TIEMPO_AGOTADO',
];

describe('errores.ts: ningún error técnico crudo llega a la pantalla', () => {
  test.each(CODIGOS)('%s tiene mensaje en español y no muestra el texto del servidor', (codigo) => {
    const e = describirError(new ErrorApi(400, codigo, 'Traceback (most recent call last): KeyError'));
    expect(ERRORES).toHaveProperty(codigo);
    expect(e.mensaje.length).toBeGreaterThan(10);
    expect(e.mensaje).not.toMatch(/Traceback|KeyError|Error:/);
  });

  test('las acciones que pide el prompt', () => {
    const accion = (c: string) => describirError(new ErrorApi(400, c, 'x')).etiqueta;
    expect(accion('SALDO_INSUFICIENTE')).toBe('Recargar');
    expect(accion('SESIONES_BLOQUEADAS')).toBe('Recargar');
    expect(accion('PUESTO_LLENO')).toBe('Buscar otro puesto');
    expect(accion('TIEMPO_AGOTADO')).toBe('Reintentar');
    expect(accion('SIN_CONEXION')).toBe('Revisar conexión');
    expect(accion('SESION_NO_EXISTE')).toBe('Volver al inicio');
  });

  test('un 502 sin cuerpo del contrato no muestra el HTML del proxy', () => {
    const e = describirError(new ErrorApi(502, 'HTTP_502', '<html><body>Bad Gateway</body></html>'));
    expect(e.mensaje).toBe('El servidor respondió con un error (502).');
    expect(e.mensaje).not.toMatch(/html/i);
  });

  test('un código desconocido o una excepción cualquiera dan un mensaje genérico', () => {
    const aviso = jest.spyOn(console, 'warn').mockImplementation(() => undefined);
    expect(describirError(new ErrorApi(418, 'CODIGO_NUEVO', 'detalle interno')).mensaje).toBe('Algo salió mal. Inténtalo de nuevo.');
    expect(describirError(new TypeError("Cannot read properties of undefined (reading 'x')")).mensaje).toBe(
      'Algo salió mal. Inténtalo de nuevo.',
    );
    expect(aviso).toHaveBeenCalled();
    aviso.mockRestore();
  });
});

test('ErrorParaUsuario conserva su texto (ya está escrito para el usuario)', () => {
  const { ErrorParaUsuario } = jest.requireActual<typeof import('@/src/errores')>('@/src/errores');
  const e = describirError(new ErrorParaUsuario('Sin permiso de ubicación: actívalo en los ajustes.'));
  expect(e.mensaje).toBe('Sin permiso de ubicación: actívalo en los ajustes.');
});
