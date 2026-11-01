import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet } from 'react-native';
import MapView, { Marker } from 'react-native-maps';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { getBilletera, getGuia, mensajeUsuario } from '@/src/api/cliente';
import { montoRetencion } from '@/src/api/tarifa';
import type { Destino } from '@/src/api/tipos';
import { DESTINOS } from '@/src/datos/destinos';
import { useSesion } from '@/src/estado/sesion';
import { PARTIDA_POR_DEFECTO, type Punto } from '@/src/sesion/geo';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';

const REGION_CENTRO = { latitude: -2.8975, longitude: -79.0045, latitudeDelta: 0.012, longitudeDelta: 0.012 };

// Todo es simulado: la partida es una esquina del Centro (o donde se toque el mapa), no el GPS.
export default function Buscar() {
  const { api, usuarioId } = useAjustes();
  const { despachar } = useSesion();
  const [partida, setPartida] = useState<Punto>(PARTIDA_POR_DEFECTO);
  const [destino, setDestino] = useState<Destino>(DESTINOS[0]);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Solo en desarrollo: ?destino=<índice>&auto=1 permite manejar la pantalla desde la terminal
  // (xcrun simctl openurl), igual que el grabador de S1.
  const params = useLocalSearchParams<{ destino?: string; auto?: string }>();

  useEffect(() => {
    if (!__DEV__) return;
    const d = DESTINOS[Number(params.destino)];
    if (d) setDestino(d);
    if (params.auto === '1') buscar(d);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.destino, params.auto]);

  async function buscar(elegido: Destino = destino) {
    setOcupado(true);
    setError(null);
    try {
      // CONTEXTO, reglas de cobro 1: sin disponible para el bloque mínimo, primero se recarga.
      const billetera = await getBilletera(usuarioId, api);
      if (billetera.bloqueada || billetera.disponible < montoRetencion()) {
        router.push('/recarga');
        return;
      }
      despachar({ tipo: 'BUSCAR', partida, destino: elegido });
      const guia = await getGuia(
        { lat: partida.lat, lon: partida.lon, destino_lat: elegido.lat, destino_lon: elegido.lon },
        api,
      );
      despachar({ tipo: 'GUIA_RECIBIDA', guia });
      router.replace('/sesion/guiar');
    } catch (e) {
      despachar({ tipo: 'REINICIAR' });
      setError(mensajeUsuario(e));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <View style={estilos.contenedor}>
      <MapView
        style={estilos.mapa}
        initialRegion={REGION_CENTRO}
        onPress={(e) => setPartida({ lat: e.nativeEvent.coordinate.latitude, lon: e.nativeEvent.coordinate.longitude })}
        onLongPress={(e) =>
          setDestino({
            nombre: 'Punto en el mapa',
            lat: e.nativeEvent.coordinate.latitude,
            lon: e.nativeEvent.coordinate.longitude,
          })
        }>
        <Marker coordinate={{ latitude: partida.lat, longitude: partida.lon }} title="Partida (simulada)">
          <Text style={estilos.emoji}>🚗</Text>
        </Marker>
        <Marker
          coordinate={{ latitude: destino.lat, longitude: destino.lon }}
          title={destino.nombre}
          pinColor={COLORES.miguel}
        />
      </MapView>
      <View style={estilos.panel}>
        <Text style={estilos.ayuda}>
          Toca el mapa para mover la partida; mantén pulsado para elegir otro destino.
        </Text>
        <Text style={estilos.etiqueta}>Destino</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={estilos.chips}>
          {DESTINOS.map((d) => {
            const elegido = d.nombre === destino.nombre;
            return (
              <Pressable
                key={d.nombre}
                onPress={() => setDestino(d)}
                style={[estilos.chip, elegido && estilos.chipElegido]}>
                <Text style={[estilos.chipTexto, elegido && estilos.chipTextoElegido]}>{d.nombre}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
        <Text style={estilos.resumen} numberOfLines={1}>
          → {destino.nombre}
        </Text>
        {error && <Text style={estilos.error}>{error}</Text>}
        <Boton texto="Buscar puesto" onPress={() => buscar()} ocupado={ocupado} />
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  contenedor: { flex: 1 },
  mapa: { flex: 1 },
  emoji: { fontSize: 26 },
  panel: { padding: 14, paddingBottom: 28 },
  ayuda: { color: COLORES.gris, fontSize: 13, marginBottom: 8 },
  etiqueta: { fontWeight: '700', marginBottom: 6 },
  chips: { gap: 8, paddingBottom: 4 },
  chip: { borderWidth: 1, borderColor: COLORES.gris, borderRadius: 16, paddingVertical: 6, paddingHorizontal: 12 },
  chipElegido: { backgroundColor: COLORES.miguel, borderColor: COLORES.miguel },
  chipTexto: { fontSize: 13 },
  chipTextoElegido: { color: '#fff', fontWeight: '700' },
  resumen: { marginTop: 8, fontSize: 16, fontWeight: '600' },
  error: { color: COLORES.lleno, marginTop: 6 },
});
