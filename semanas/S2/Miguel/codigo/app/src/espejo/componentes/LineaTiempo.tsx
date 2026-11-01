import { StyleSheet, View } from 'react-native';

import { Text } from '@/components/Themed';
import { ESTADOS_SESION, type EstadoSesion } from '@/src/api/tipos';
import { COLORES } from '@/src/ui/colores';
import { NOMBRE_ESTADO, mmss } from '../formato';

/** Los 7 estados en horizontal: el actual resaltado y los pasados con el t_sim en que empezaron. */
export function LineaTiempo({
  actual,
  inicios,
}: {
  actual: EstadoSesion | null;
  inicios: Partial<Record<EstadoSesion, number>>;
}) {
  const iActual = actual ? ESTADOS_SESION.indexOf(actual) : -1;
  return (
    <View style={estilos.fila}>
      {ESTADOS_SESION.map((e, i) => {
        const pasado = i < iActual || (i === iActual && e === 'CERRADA');
        const esActual = i === iActual;
        const color = esActual ? COLORES.miguel : pasado ? COLORES.libre : '#BDBDBD';
        return (
          <View key={e} style={estilos.paso}>
            <View style={estilos.lineaYPunto}>
              <View style={[estilos.linea, i === 0 && estilos.invisible, { backgroundColor: i <= iActual ? COLORES.libre : '#BDBDBD' }]} />
              <View style={[estilos.punto, { backgroundColor: color }, esActual && estilos.puntoActual]} />
              <View
                style={[
                  estilos.linea,
                  i === ESTADOS_SESION.length - 1 && estilos.invisible,
                  { backgroundColor: i < iActual ? COLORES.libre : '#BDBDBD' },
                ]}
              />
            </View>
            <Text style={[estilos.nombre, esActual && estilos.nombreActual]} numberOfLines={1}>
              {NOMBRE_ESTADO[e]}
            </Text>
            <Text style={estilos.tiempo}>{inicios[e] !== undefined ? mmss(inicios[e]!) : ' '}</Text>
          </View>
        );
      })}
    </View>
  );
}

const estilos = StyleSheet.create({
  fila: { flexDirection: 'row' },
  paso: { flex: 1, alignItems: 'center' },
  lineaYPunto: { flexDirection: 'row', alignItems: 'center', alignSelf: 'stretch' },
  linea: { flex: 1, height: 3 },
  invisible: { opacity: 0 },
  punto: { width: 12, height: 12, borderRadius: 6 },
  puntoActual: { width: 18, height: 18, borderRadius: 9, borderWidth: 3, borderColor: '#FFCDD2' },
  nombre: { fontSize: 9, marginTop: 3, color: COLORES.gris },
  nombreActual: { color: COLORES.miguel, fontWeight: '800' },
  tiempo: { fontSize: 9, color: COLORES.gris, fontVariant: ['tabular-nums'] },
});
