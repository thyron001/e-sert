import { StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import type { Conexion } from '@/src/espejo/usarEspejo';
import { COLORES } from '@/src/ui/colores';

const TEXTO = { en_vivo: 'En vivo', reconectando: 'Reconectando', sin_conexion: 'Sin conexión', finalizado: 'Finalizado' } as const;
const COLOR = { en_vivo: COLORES.libre, reconectando: '#F9A825', sin_conexion: COLORES.lleno, finalizado: COLORES.gris } as const;

/** Punto de color y texto del estado del WebSocket, para la cabecera del espejo. */
export function IndicadorConexion({ conexion }: { conexion: Conexion }) {
  const intento = (conexion.estado === 'reconectando' || conexion.estado === 'sin_conexion') && conexion.intento > 0 ? ` (${conexion.intento})` : '';
  return (
    <View style={estilos.fila}>
      <View style={[estilos.punto, { backgroundColor: COLOR[conexion.estado] }]} />
      <Text style={estilos.texto}>
        {TEXTO[conexion.estado]}
        {intento}
      </Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  // marginRight deja libre el botón flotante de Ajustes de la esquina.
  fila: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: 'transparent', marginRight: 52 },
  punto: { width: 10, height: 10, borderRadius: 5 },
  texto: { fontSize: 13, fontWeight: '600' },
});
