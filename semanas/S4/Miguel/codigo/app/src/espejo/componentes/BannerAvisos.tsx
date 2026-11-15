import { StyleSheet, Text, View } from 'react-native';

import type { Aviso } from '@/src/api/tipos';
import { TEXTO_AVISO } from '../formato';

/** Franja amarilla con los avisos del backend (saldo bajo, tiempo máximo...). Nada si no hay. */
export function BannerAvisos({ avisos }: { avisos: Aviso[] }) {
  if (avisos.length === 0) return null;
  return (
    <View style={estilos.banner}>
      {avisos.map((a) => (
        <Text key={a} style={estilos.texto}>
          ⚠️ {TEXTO_AVISO[a] ?? a}
        </Text>
      ))}
    </View>
  );
}

const estilos = StyleSheet.create({
  banner: {
    backgroundColor: '#FFF3CD',
    borderColor: '#F0AD4E',
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginBottom: 8,
  },
  texto: { color: '#7A4F01', fontWeight: '600' },
});
