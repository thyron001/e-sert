import { ActivityIndicator, Pressable, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';

import { Text } from '@/components/Themed';
import { COLORES } from './colores';

export function Boton({
  texto,
  onPress,
  ocupado = false,
  deshabilitado = false,
  style,
}: {
  texto: string;
  onPress: () => void;
  ocupado?: boolean;
  deshabilitado?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const inactivo = ocupado || deshabilitado;
  return (
    <Pressable
      style={[estilos.boton, inactivo && estilos.inactivo, style]}
      onPress={onPress}
      disabled={inactivo}
      accessibilityRole="button"
      accessibilityLabel={texto}
      accessibilityState={{ disabled: inactivo, busy: ocupado }}>
      {ocupado ? <ActivityIndicator color="#fff" /> : <Text style={estilos.texto}>{texto}</Text>}
    </Pressable>
  );
}

/** Fecha y hora locales del teléfono, p. ej. "27/10 10:42". */
export function fechaLocal(iso: string): string {
  // Hora de Ecuador (UTC−5, sin horario de verano), aunque el teléfono esté en otra zona.
  const d = new Date(Date.parse(iso) - 5 * 3600_000);
  const dos = (n: number) => String(n).padStart(2, '0');
  return `${dos(d.getUTCDate())}/${dos(d.getUTCMonth() + 1)} ${dos(d.getUTCHours())}:${dos(d.getUTCMinutes())}`;
}

/** Moneda en el formato de Ecuador: $0,50 (coma decimal). */
export const usd = (v: number) => `${v < 0 ? '−' : ''}$${Math.abs(v).toFixed(2).replace('.', ',')}`;

const estilos = StyleSheet.create({
  boton: {
    backgroundColor: COLORES.miguel,
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 44, // objetivo táctil de al menos 44 pt
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 8,
  },
  inactivo: { opacity: 0.5 },
  texto: { color: '#fff', fontWeight: '600' },
});
