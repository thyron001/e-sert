import { StyleSheet, View } from 'react-native';

import { Text } from '@/components/Themed';
import type { BilleteraEspejo, SesionEspejo } from '@/src/api/tipos';
import { COLORES } from '@/src/ui/colores';
import { usd } from '../formato';

function Dato({ etiqueta, valor, grande = false }: { etiqueta: string; valor: string; grande?: boolean }) {
  return (
    <View style={estilos.dato}>
      <Text style={[estilos.valor, grande && estilos.grande]}>{valor}</Text>
      <Text style={estilos.etiqueta}>{etiqueta}</Text>
    </View>
  );
}

/** Minutos y costo en curso de la sesión, más lo retenido y lo disponible de la billetera. */
export function CostoVivo({ sesion, billetera }: { sesion: SesionEspejo | null; billetera: BilleteraEspejo | null }) {
  return (
    <View style={estilos.fila}>
      <Dato etiqueta="minutos" valor={sesion ? sesion.minutos.toFixed(1).replace('.', ',') : '—'} grande />
      <Dato etiqueta="costo" valor={sesion ? usd(sesion.costo_usd) : '—'} grande />
      <Dato etiqueta="retenido" valor={sesion ? usd(sesion.retenido_usd) : '—'} />
      <Dato etiqueta="disponible" valor={billetera ? usd(billetera.disponible) : '—'} />
    </View>
  );
}

const estilos = StyleSheet.create({
  fila: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  dato: { alignItems: 'center', flex: 1 },
  valor: { fontSize: 16, fontWeight: '700', fontVariant: ['tabular-nums'] },
  grande: { fontSize: 22, color: COLORES.miguel },
  etiqueta: { fontSize: 11, color: COLORES.gris },
});
