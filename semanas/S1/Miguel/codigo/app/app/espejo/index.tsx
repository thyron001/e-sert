import { router } from 'expo-router';
import { FlatList, Pressable, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { candidatosMock } from '@/src/espejo/recorridoMock';
import { NOMBRE_ESTADO, mmss } from '@/src/espejo/formato';
import { COLORES } from '@/src/ui/colores';

// MOCK: reemplazar candidatosMock() por GET /api/v1/espejo/candidatos cuando exista el backend (S2-3).
export default function SelectorEspejo() {
  const candidatos = candidatosMock();
  return (
    <FlatList
      data={candidatos}
      keyExtractor={(c) => c.id}
      contentContainerStyle={estilos.lista}
      contentInsetAdjustmentBehavior="automatic"
      ListHeaderComponent={
        <Text style={estilos.ayuda}>
          Elige un conductor simulado de SUMO. El teléfono mostrará lo que ve su conductor: guiado al puesto, sesión,
          costo en vivo y recibo. El teléfono no se mueve.
        </Text>
      }
      renderItem={({ item }) => (
        <Pressable
          style={({ pressed }) => [estilos.fila, pressed && estilos.presionado]}
          onPress={() => router.push({ pathname: '/espejo/[vehId]', params: { vehId: item.id } })}>
          <View style={estilos.icono}>
            <Text style={estilos.emoji}>🚗</Text>
          </View>
          <View style={estilos.textos}>
            <Text style={estilos.id}>{item.id}</Text>
            <Text style={estilos.destino}>→ {item.destino_nombre}</Text>
          </View>
          <View style={estilos.derecha}>
            <Text style={estilos.estado}>{item.estado ? NOMBRE_ESTADO[item.estado] : 'Sin buscar aún'}</Text>
            <Text style={estilos.tiempo}>t_sim {mmss(item.t_sim)}</Text>
          </View>
        </Pressable>
      )}
      ItemSeparatorComponent={() => <View style={estilos.separador} />}
    />
  );
}

const estilos = StyleSheet.create({
  lista: { padding: 16 },
  ayuda: { color: COLORES.gris, marginBottom: 12 },
  fila: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12 },
  presionado: { opacity: 0.5 },
  icono: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#FFEBEE',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  emoji: { fontSize: 22 },
  textos: { flex: 1, backgroundColor: 'transparent' },
  id: { fontSize: 16, fontWeight: '700' },
  destino: { color: COLORES.gris, marginTop: 2 },
  derecha: { alignItems: 'flex-end', backgroundColor: 'transparent' },
  estado: { fontWeight: '700', color: COLORES.miguel },
  tiempo: { fontSize: 12, color: COLORES.gris, fontVariant: ['tabular-nums'] },
  separador: { height: StyleSheet.hairlineWidth, backgroundColor: COLORES.gris },
});
