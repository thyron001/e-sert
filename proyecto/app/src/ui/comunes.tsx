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
      disabled={inactivo}>
      {ocupado ? <ActivityIndicator color="#fff" /> : <Text style={estilos.texto}>{texto}</Text>}
    </Pressable>
  );
}

/** Fecha y hora locales del teléfono, p. ej. "27/10 10:42". */
export function fechaLocal(iso: string): string {
  const d = new Date(iso);
  const dos = (n: number) => String(n).padStart(2, '0');
  return `${dos(d.getDate())}/${dos(d.getMonth() + 1)} ${dos(d.getHours())}:${dos(d.getMinutes())}`;
}

export const usd = (v: number) => `${v < 0 ? '−' : ''}$${Math.abs(v).toFixed(2)}`;

const estilos = StyleSheet.create({
  boton: {
    backgroundColor: COLORES.miguel,
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  inactivo: { opacity: 0.5 },
  texto: { color: '#fff', fontWeight: '600' },
});
