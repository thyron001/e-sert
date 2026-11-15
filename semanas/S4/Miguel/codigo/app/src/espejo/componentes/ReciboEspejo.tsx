import { Modal, StyleSheet, View as VistaRN } from 'react-native';

import { Text, View } from '@/components/Themed';
import type { ReciboEspejo as Recibo } from '@/src/api/tipos';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';
import { usd } from '../formato';

function Fila({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <View style={estilos.fila}>
      <Text style={estilos.etiqueta}>{etiqueta}</Text>
      <Text style={estilos.valor}>{valor}</Text>
    </View>
  );
}

/** Recibo al cerrar la sesión: lo cobrado frente a lo que habría costado con la tarjeta SERT. */
export function ReciboEspejo({
  recibo,
  visible,
  alCerrar,
}: {
  recibo: Recibo | null;
  visible: boolean;
  alCerrar: () => void;
}) {
  if (!recibo) return null;
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={alCerrar}>
      <VistaRN style={estilos.fondo}>
        <View style={estilos.tarjeta}>
          <Text style={estilos.titulo}>Recibo de parqueo</Text>
          <Fila etiqueta="Tiempo real" valor={`${recibo.minutos_reales} min`} />
          <Fila etiqueta="Tiempo cobrado (fracciones de 5 min)" valor={`${recibo.minutos_cobrados} min`} />
          <View style={estilos.separador} />
          <Fila etiqueta="Cobrado" valor={usd(recibo.cobrado_usd)} />
          <Text style={estilos.comparacion}>
            Con la tarjeta SERT habrías pagado {usd(recibo.tarjeta_sert_usd)}
          </Text>
          <Text style={estilos.ahorro}>Ahorraste {usd(recibo.ahorro_usd)}</Text>
          <Boton texto="Listo" onPress={alCerrar} />
        </View>
      </VistaRN>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  fondo: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.35)' },
  tarjeta: { padding: 20, paddingBottom: 36, borderTopLeftRadius: 18, borderTopRightRadius: 18 },
  titulo: { fontSize: 20, fontWeight: '800', marginBottom: 12 },
  fila: { flexDirection: 'row', justifyContent: 'space-between', marginVertical: 4, backgroundColor: 'transparent' },
  etiqueta: { color: COLORES.gris, flex: 1 },
  valor: { fontWeight: '700', fontSize: 16 },
  separador: { height: StyleSheet.hairlineWidth, backgroundColor: COLORES.gris, marginVertical: 8 },
  comparacion: { marginTop: 8, fontSize: 15 },
  ahorro: { marginTop: 4, fontSize: 22, fontWeight: '800', color: COLORES.libre },
});
