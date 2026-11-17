import { router } from 'expo-router';
import { StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { describirError } from '@/src/errores';
import { COLORES } from './colores';
import { Boton } from './comunes';

/**
 * Muestra un error ya traducido (src/errores.ts) con su acción: Recargar, Buscar otro puesto,
 * Reintentar, Revisar conexión o Volver al inicio. `alReintentar` es obligatorio para reintentar.
 */
export function AvisoError({ error, alReintentar }: { error: unknown; alReintentar?: () => void }) {
  if (error === null || error === undefined) return null;
  const e = describirError(error);
  const accion = (): void => {
    switch (e.accion) {
      case 'recargar':
        return router.push('/recarga');
      case 'buscar_otro':
        return router.replace('/buscar');
      case 'ajustes':
        return router.push('/demo');
      case 'volver':
        return router.replace('/sesion');
      case 'reintentar':
        return alReintentar?.();
    }
  };
  const conBoton = e.etiqueta && (e.accion !== 'reintentar' || alReintentar);
  return (
    <View style={estilos.caja} accessibilityRole="alert" accessibilityLiveRegion="polite">
      <Text style={estilos.texto}>{e.mensaje}</Text>
      {conBoton && <Boton texto={e.etiqueta!} onPress={accion} style={estilos.boton} />}
    </View>
  );
}

const estilos = StyleSheet.create({
  caja: {
    marginTop: 8,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORES.lleno,
    backgroundColor: 'rgba(198,40,40,0.08)',
  },
  texto: { color: COLORES.lleno, fontWeight: '600' },
  boton: { marginTop: 8 },
});
