import { describe, expect, it } from '@jest/globals';

import { esPlacaValida, normalizarPlaca } from '@/src/sesion/placa';

describe('placa ecuatoriana (CONTRATO §4.3)', () => {
  it.each(['ABC-1234', 'ABC123', 'ABC-123', 'ABC1234', 'SIM-0042'])('acepta %s', (placa) => {
    expect(esPlacaValida(placa)).toBe(true);
  });

  it.each(['AB-123', 'abc1234x', 'ABCD-123', 'ABC-12345', '', 'abc-1234', 'ABC 1234'])(
    'rechaza "%s"',
    (placa) => {
      expect(esPlacaValida(placa)).toBe(false);
    },
  );

  it('normaliza a mayúsculas y sin espacios', () => {
    expect(normalizarPlaca('abc 1234')).toBe('ABC1234');
    expect(esPlacaValida(normalizarPlaca('abc 1234'))).toBe(true);
    expect(normalizarPlaca(' abc-123 ')).toBe('ABC-123');
  });

  it('normalizar no arregla una placa mal formada', () => {
    expect(normalizarPlaca('abc1234x')).toBe('ABC1234X');
    expect(esPlacaValida(normalizarPlaca('abc1234x'))).toBe(false);
  });
});
