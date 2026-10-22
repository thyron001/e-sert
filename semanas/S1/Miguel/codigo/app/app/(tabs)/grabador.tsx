import { StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { COLORES } from '@/src/ui/colores';

// Se implementa en S1 · Sesión 2 (grabador de sensores etiquetado).
export default function GrabadorScreen() {
  return (
    <View style={styles.contenedor}>
      <Text style={styles.titulo}>Grabador de sensores</Text>
      <Text style={styles.texto}>
        Aquí se grabarán trazas etiquetadas de GPS (1 Hz) y acelerómetro (10 Hz) para la validación
        opcional del clasificador. Llega en la sesión 2.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  contenedor: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  titulo: { fontSize: 20, fontWeight: '700' },
  texto: { marginTop: 8, textAlign: 'center', color: COLORES.gris },
});
