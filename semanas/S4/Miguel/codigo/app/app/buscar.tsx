import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MapView, { Marker } from 'react-native-maps';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { baseAsistente } from '@/src/api/asistente';
import { getBilletera, getGuia } from '@/src/api/cliente';
import { EntradaNatural } from '@/src/componentes/EntradaNatural';
import { montoRetencion } from '@/src/api/tarifa';
import type { Destino } from '@/src/api/tipos';
import { DESTINOS } from '@/src/datos/destinos';
import { useSesion } from '@/src/estado/sesion';
import { PARTIDA_POR_DEFECTO, type Punto } from '@/src/sesion/geo';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';
import { AvisoError } from '@/src/ui/AvisoError';

const REGION_CENTRO = { latitude: -2.8975, longitude: -79.0045, latitudeDelta: 0.012, longitudeDelta: 0.012 };

// Todo es simulado: la partida es una esquina del Centro (o donde se toque el mapa), no el GPS.
export default function Buscar() {
  const { api, usuarioId, urlApi } = useAjustes();
  const insets = useSafeAreaInsets();
  const { despachar } = useSesion();
  const [partida, setPartida] = useState<Punto>(PARTIDA_POR_DEFECTO);
  const [destino, setDestino] = useState<Destino>(DESTINOS[0]);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<unknown>(null);
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

  async function buscar(elegido: Destino = destino, duracionPlanMin: number | null = null) {
    setOcupado(true);
    setError(null);
    try {
      // CONTEXTO, reglas de cobro 1: sin disponible para el bloque mínimo, primero se recarga.
      const billetera = await getBilletera(usuarioId, api);
      if (billetera.bloqueada || billetera.disponible < montoRetencion()) {
        router.push('/recarga');
        return;
      }
      despachar({ tipo: 'BUSCAR', partida, destino: elegido, duracionPlanMin });
      const guia = await getGuia(
        { lat: partida.lat, lon: partida.lon, destino_lat: elegido.lat, destino_lon: elegido.lon },
        api,
      );
      despachar({ tipo: 'GUIA_RECIBIDA', guia });
      router.replace('/sesion/guiar');
    } catch (e) {
      despachar({ tipo: 'REINICIAR' });
      setError(e);
    } finally {
      setOcupado(false);
    }
  }

  return (
    // Al abrir el teclado el panel sube (en Android con edge-to-edge la pantalla no se encoge sola).
    // El desplazamiento es la cabecera de la pila: barra de estado + 56 (Android) o 44 (iOS).
    <KeyboardAvoidingView
      style={estilos.contenedor}
      behavior="padding"
      keyboardVerticalOffset={insets.top + (Platform.OS === 'ios' ? 44 : 56)}>
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
        <EntradaNatural
          urlBase={baseAsistente(urlApi)}
          destinoInicial={DESTINOS[0]}
          ocupado={ocupado}
          alBuscar={(d, minutos) => {
            setDestino(d);
            buscar(d, minutos);
          }}
        />
        {destino.nombre === 'Punto en el mapa' && (
          <>
            <Text style={estilos.resumen} numberOfLines={1}>
              → {destino.nombre}
            </Text>
            <Boton texto="Buscar en el punto marcado" onPress={() => buscar()} ocupado={ocupado} />
          </>
        )}
        <AvisoError error={error} alReintentar={() => buscar()} />
      </View>
    </KeyboardAvoidingView>
  );
}

const estilos = StyleSheet.create({
  contenedor: { flex: 1 },
  mapa: { flex: 1 },
  emoji: { fontSize: 26 },
  panel: { padding: 14, paddingBottom: 28 },
  ayuda: { color: COLORES.gris, fontSize: 13, marginBottom: 8 },
  resumen: { marginTop: 8, fontSize: 16, fontWeight: '600' },
  error: { color: COLORES.lleno, marginTop: 6 },
});
