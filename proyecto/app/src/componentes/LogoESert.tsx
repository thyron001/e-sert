import { router } from 'expo-router';
import { Image, Pressable, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { COLORES } from '@/src/ui/colores';

/** Logo y nombre de la app. Mantenerlo pulsado 3 s abre "Ajustes de demo" (pantalla oculta). */
export function LogoESert() {
  return (
    <Pressable
      onLongPress={() => router.push('/demo')}
      delayLongPress={3000}
      accessibilityRole="header"
      accessibilityLabel="e-sert, parqueo SERT en el Centro de Cuenca"
      accessibilityHint="Mantén pulsado 3 segundos para abrir los ajustes de la demo">
      <View style={estilos.fila}>
        <Image source={require('@/assets/images/icon.png')} style={estilos.logo} />
        <View style={estilos.textos}>
          <Text style={estilos.nombre}>e-sert</Text>
          <Text style={estilos.lema}>Parqueo SERT · Centro Histórico de Cuenca</Text>
        </View>
      </View>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  fila: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 4, backgroundColor: 'transparent' },
  logo: { width: 48, height: 48, borderRadius: 12 },
  textos: { backgroundColor: 'transparent' },
  nombre: { fontSize: 24, fontWeight: '800', color: COLORES.miguel },
  lema: { fontSize: 13, color: COLORES.gris },
});
