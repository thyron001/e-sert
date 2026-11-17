import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { mensajeUsuario } from '@/src/api/cliente';
import { baseEspejo, getCandidatos } from '@/src/api/espejo';
import type { CandidatoEspejo } from '@/src/api/tipos';
import { candidatosMock } from '@/src/espejo/recorridoMock';
import { NOMBRE_ESTADO, mmss } from '@/src/espejo/formato';
import { COLORES } from '@/src/ui/colores';

// Candidatos de GET /api/v1/espejo/candidatos; con el modo mock de la app, los del recorrido interno.
export default function SelectorEspejo() {
  const { urlApi, modoMock } = useAjustes();
  const [candidatos, setCandidatos] = useState<CandidatoEspejo[]>(() => (modoMock ? candidatosMock() : []));
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (modoMock) return setCandidatos(candidatosMock());
    setCargando(true);
    setError(null);
    try {
      setCandidatos(await getCandidatos(baseEspejo(urlApi)));
    } catch (e) {
      setError(mensajeUsuario(e));
    } finally {
      setCargando(false);
    }
  }, [urlApi, modoMock]);

  useFocusEffect(
    useCallback(() => {
      cargar();
    }, [cargar]),
  );

  return (
    <FlatList
      data={candidatos}
      refreshControl={<RefreshControl refreshing={cargando} onRefresh={cargar} tintColor={COLORES.miguel} />}
      keyExtractor={(c) => c.id}
      contentContainerStyle={estilos.lista}
      contentInsetAdjustmentBehavior="automatic"
      ListHeaderComponent={
        <Text style={estilos.ayuda}>
          Elige un conductor simulado de SUMO. El teléfono mostrará lo que ve su conductor: guiado al puesto, sesión,
          costo en vivo y recibo. El teléfono no se mueve.
          {'\n'}Fuente: {modoMock ? 'recorrido interno (mock de la app)' : baseEspejo(urlApi)}
          {error ? `\n${error}` : ''}
        </Text>
      }
      ListEmptyComponent={
        cargando ? undefined : (
          <Text style={estilos.ayuda}>No hay autos con app en la simulación ahora. Desliza para actualizar.</Text>
        )
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
