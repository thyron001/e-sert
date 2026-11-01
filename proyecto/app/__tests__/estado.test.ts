import { describe, expect, it, jest } from '@jest/globals';

jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);

import {
  FLUJO_INICIAL,
  cargarFlujo,
  guardarFlujo,
  reductor,
  rutaDelFlujo,
  sesionAbierta,
  type Accion,
  type EstadoFlujo,
} from '@/src/estado/sesion';

const partida = { lat: -2.895833, lon: -79.004625 };
const destino = { nombre: 'Parque Calderón', lat: -2.897308, lon: -79.004488 };
const guia = { puesto_id: 'pa_-100644#0_0', lat: -2.8968, lon: -79.0047, distancia_m: 60 };
const sesion = {
  sesion_id: 'ses_91ab3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d',
  placa: 'ABC-1234',
  puesto_id: guia.puesto_id,
  inicio: '2026-10-27T15:00:00.000Z',
  retenido: 0.25,
};

const aplicar = (acciones: Accion[], e: EstadoFlujo = FLUJO_INICIAL) => acciones.reduce(reductor, e);

describe('reductor del flujo de sesión', () => {
  it('recorre BUSCANDO → GUIADO → ESTACIONADO → CERRADA', () => {
    const buscando = aplicar([{ tipo: 'BUSCAR', partida, destino }]);
    expect(buscando.estado).toBe('BUSCANDO');
    const guiado = reductor(buscando, { tipo: 'GUIA_RECIBIDA', guia });
    expect(guiado.estado).toBe('GUIADO');
    expect(guiado.posicion).toEqual(partida);
    expect(rutaDelFlujo(guiado)).toBe('/sesion/guiar');
    const estacionado = reductor(guiado, { tipo: 'SESION_CREADA', sesion });
    expect(estacionado.estado).toBe('ESTACIONADO');
    expect(estacionado.ultimaPlaca).toBe('ABC-1234');
    expect(sesionAbierta(estacionado)).toBe(true);
    expect(rutaDelFlujo(estacionado)).toBe('/sesion/activa');
    const cerrada = reductor(estacionado, {
      tipo: 'CERRADA',
      cierre: { sesion_id: sesion.sesion_id, minutos_reales: 12, minutos_cobrados: 15, debitado: 0.13, saldo: 4.87 },
    });
    expect(cerrada.estado).toBe('CERRADA');
    expect(sesionAbierta(cerrada)).toBe(false);
  });

  it('AVANZAR solo mueve la posición durante el guiado', () => {
    const e = aplicar([{ tipo: 'AVANZAR', posicion: guia }]);
    expect(e.posicion).toBeNull();
  });

  it('con una sesión abierta no se puede buscar otro puesto', () => {
    const abierta = aplicar([{ tipo: 'BUSCAR', partida, destino }, { tipo: 'GUIA_RECIBIDA', guia }, { tipo: 'SESION_CREADA', sesion }]);
    expect(reductor(abierta, { tipo: 'BUSCAR', partida, destino })).toBe(abierta);
  });

  it('REINICIAR conserva la última placa', () => {
    const e = aplicar([{ tipo: 'BUSCAR', partida, destino }, { tipo: 'GUIA_RECIBIDA', guia }, { tipo: 'SESION_CREADA', sesion }, { tipo: 'REINICIAR' }]);
    expect(e).toEqual({ ...FLUJO_INICIAL, ultimaPlaca: 'ABC-1234' });
  });
});

describe('persistencia en AsyncStorage', () => {
  it('una sesión activa guardada se recupera al reabrir la app', async () => {
    const activa = aplicar([{ tipo: 'BUSCAR', partida, destino }, { tipo: 'GUIA_RECIBIDA', guia }, { tipo: 'SESION_CREADA', sesion }]);
    await guardarFlujo(activa);
    const leido = await cargarFlujo();
    expect(leido).toEqual(activa);
    const restaurado = reductor(FLUJO_INICIAL, { tipo: 'RESTAURAR', estado: leido! });
    expect(rutaDelFlujo(restaurado)).toBe('/sesion/activa');
  });
});
