import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { getBilletera, mensajeUsuario } from '@/src/api/cliente';
import type { Billetera, Movimiento, TipoMovimiento } from '@/src/api/tipos';
import { COLORES } from '@/src/ui/colores';
import { Boton, fechaLocal, usd } from '@/src/ui/comunes';

const NOMBRES: Record<TipoMovimiento, string> = {
  recarga: 'Recarga',
  retencion: 'Retención',
  debito: 'Cobro de sesión',
  liberacion: 'Retención liberada',
};

// Signo con el que cada movimiento afecta al disponible (CONTRATO §5: libro de movimientos).
const SIGNO: Record<TipoMovimiento, 1 | -1> = { recarga: 1, retencion: -1, debito: -1, liberacion: 1 };

export default function BilleteraScreen() {
  const { api, usuarioId, cargado } = useAjustes();
  const [billetera, setBilletera] = useState<Billetera | null>(null);
  const [refrescando, setRefrescando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!cargado) return;
    setError(null);
    try {
      setBilletera(await getBilletera(usuarioId, api));
    } catch (e) {
      setError(mensajeUsuario(e));
    }
  }, [api, usuarioId, cargado]);

  useFocusEffect(
    useCallback(() => {
      cargar();
    }, [cargar]),
  );

  async function refrescar() {
    setRefrescando(true);
    await cargar();
    setRefrescando(false);
  }

  const movimientos = [...(billetera?.movimientos ?? [])].sort((a, b) => b.ts.localeCompare(a.ts));

  return (
    <FlatList
      style={styles.lista}
      contentContainerStyle={styles.contenedor}
      data={movimientos}
      keyExtractor={(m) => m.movimiento_id}
      refreshControl={<RefreshControl refreshing={refrescando} onRefresh={refrescar} tintColor={COLORES.miguel} />}
      ListHeaderComponent={
        <View>
          <View style={styles.tarjeta}>
            <Text style={styles.etiqueta}>Disponible</Text>
            <Text style={styles.grande}>{billetera ? usd(billetera.disponible) : '…'}</Text>
            <Text style={styles.detalle}>
              Saldo {billetera ? usd(billetera.saldo) : '…'} · Retenido {billetera ? usd(billetera.retenido) : '…'}
            </Text>
            {billetera?.bloqueada && (
              <Text style={styles.error}>Saldo negativo: recarga para volver a parquear.</Text>
            )}
          </View>
          <Boton texto="Recargar con Payphone" onPress={() => router.push('/recarga')} />
          {error && <Text style={styles.error}>{error}</Text>}
          <Text style={styles.subtitulo}>Movimientos</Text>
        </View>
      }
      renderItem={({ item }) => <FilaMovimiento m={item} />}
      ListEmptyComponent={<Text style={styles.detalle}>Sin movimientos. Desliza hacia abajo para actualizar.</Text>}
    />
  );
}

function FilaMovimiento({ m }: { m: Movimiento }) {
  const signo = SIGNO[m.tipo];
  return (
    <View style={styles.mov}>
      <View style={styles.movTexto}>
        <Text style={styles.tipo}>{NOMBRES[m.tipo]}</Text>
        <Text style={styles.ts}>
          {fechaLocal(m.ts)}
          {m.referencia_payphone ? ` · Payphone ${m.referencia_payphone}` : ''}
        </Text>
      </View>
      <Text style={[styles.monto, { color: signo > 0 ? COLORES.libre : COLORES.lleno }]}>
        {signo > 0 ? '+' : '−'}
        {usd(m.monto)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  lista: { flex: 1 },
  contenedor: { padding: 16 },
  tarjeta: { padding: 16, borderRadius: 12, borderWidth: 1, borderColor: COLORES.miguel },
  etiqueta: { fontSize: 13, color: COLORES.gris },
  grande: { fontSize: 36, fontWeight: '700' },
  detalle: { color: COLORES.gris, marginTop: 4 },
  subtitulo: { fontSize: 16, fontWeight: '600', marginTop: 20, marginBottom: 6 },
  error: { color: COLORES.lleno, marginTop: 6 },
  mov: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: COLORES.gris,
  },
  movTexto: { flex: 1, backgroundColor: 'transparent' },
  tipo: { fontWeight: '600' },
  ts: { color: COLORES.gris, fontSize: 12, marginTop: 2 },
  monto: { width: 90, textAlign: 'right', fontWeight: '700', fontVariant: ['tabular-nums'] },
});
