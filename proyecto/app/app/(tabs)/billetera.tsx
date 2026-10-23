import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { FlatList, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { TARIFA } from '@/src/api/tarifa';
import type { Billetera } from '@/src/api/tipos';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

export default function BilleteraScreen() {
  const { api, usuarioId, cargado } = useAjustes();
  const [billetera, setBilletera] = useState<Billetera | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!cargado) return;
    setError(null);
    try {
      setBilletera(await api.obtenerBilletera(usuarioId));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [api, usuarioId, cargado]);

  useFocusEffect(
    useCallback(() => {
      cargar();
    }, [cargar]),
  );

  // Recarga de prueba directa al libro. Payphone (modo de pruebas) llega en una sesión posterior.
  async function recargar() {
    setOcupado(true);
    setError(null);
    try {
      await api.recargar(usuarioId, { monto: TARIFA.recarga_minima_usd });
      await cargar();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <View style={styles.contenedor}>
      <View style={styles.tarjeta}>
        <Text style={styles.etiqueta}>Disponible</Text>
        <Text style={styles.grande}>{billetera ? usd(billetera.disponible) : '…'}</Text>
        <Text style={styles.detalle}>
          Saldo {billetera ? usd(billetera.saldo) : '…'} · Retenido {billetera ? usd(billetera.retenido) : '…'}
        </Text>
      </View>
      <Boton
        texto={`Recargar ${usd(TARIFA.recarga_minima_usd)} (prueba)`}
        onPress={recargar}
        ocupado={ocupado}
      />
      {error && <Text style={styles.error}>{error}</Text>}
      <Text style={styles.subtitulo}>Movimientos</Text>
      <FlatList
        data={[...(billetera?.movimientos ?? [])].reverse()}
        keyExtractor={(m) => m.movimiento_id}
        renderItem={({ item }) => (
          <View style={styles.mov}>
            <Text style={styles.tipo}>{item.tipo}</Text>
            <Text style={styles.ts}>{new Date(item.ts).toLocaleTimeString()}</Text>
            <Text style={styles.monto}>{usd(item.monto)}</Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.detalle}>Sin movimientos.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  contenedor: { flex: 1, padding: 16 },
  tarjeta: { padding: 16, borderRadius: 12, borderWidth: 1, borderColor: COLORES.miguel },
  etiqueta: { fontSize: 13, color: COLORES.gris },
  grande: { fontSize: 36, fontWeight: '700' },
  detalle: { color: COLORES.gris, marginTop: 4 },
  subtitulo: { fontSize: 16, fontWeight: '600', marginTop: 20, marginBottom: 6 },
  error: { color: COLORES.lleno, marginTop: 6 },
  mov: { flexDirection: 'row', paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: COLORES.gris },
  tipo: { flex: 1, fontWeight: '500' },
  ts: { color: COLORES.gris, marginRight: 12 },
  monto: { width: 70, textAlign: 'right' },
});
