import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';
import { StyleSheet } from 'react-native';
import MapView, { Marker, Polyline } from 'react-native-maps';

import { Text, View } from '@/components/Themed';
import { useSesion } from '@/src/estado/sesion';
import { RADIO_LLEGADA_M, VELOCIDAD_SIM_MPS, haversineM, simularAvance } from '@/src/sesion/geo';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';

// Guiado simulado: la posición avanza sola a ~8 m/s en línea recta hacia el puesto (1 Hz).
export default function Guiar() {
  const { flujo, despachar } = useSesion();
  const { guia, posicion, destino } = flujo;
  const mapa = useRef<MapView>(null);
  const posRef = useRef(posicion);
  posRef.current = posicion;

  const distancia = guia && posicion ? haversineM(posicion, guia) : null;

  // El temporizador vive solo mientras la pantalla tiene el foco: se limpia al salir.
  useFocusEffect(
    useCallback(() => {
      if (!guia) return;
      const id = setInterval(() => {
        const actual = posRef.current;
        if (actual) despachar({ tipo: 'AVANZAR', posicion: simularAvance(actual, guia, VELOCIDAD_SIM_MPS) });
      }, 1000);
      return () => clearInterval(id);
    }, [guia, despachar]),
  );

  useEffect(() => {
    if (distancia !== null && distancia < RADIO_LLEGADA_M) router.replace('/sesion/confirmar');
  }, [distancia]);

  // Al recuperar una sesión, si el estado ya no es GUIADO, esta pantalla no aplica.
  useEffect(() => {
    if (flujo.estado !== 'GUIADO') router.replace('/sesion');
  }, [flujo.estado]);

  useEffect(() => {
    if (posicion) mapa.current?.animateCamera({ center: { latitude: posicion.lat, longitude: posicion.lon } }, { duration: 800 });
  }, [posicion]);

  if (!guia || !posicion) return null;

  const segundos = distancia !== null ? Math.ceil(Math.max(0, distancia - RADIO_LLEGADA_M) / VELOCIDAD_SIM_MPS) : 0;

  return (
    <View style={estilos.contenedor}>
      <MapView
        ref={mapa}
        style={estilos.mapa}
        initialRegion={{ latitude: posicion.lat, longitude: posicion.lon, latitudeDelta: 0.006, longitudeDelta: 0.006 }}>
        <Polyline
          coordinates={[
            { latitude: posicion.lat, longitude: posicion.lon },
            { latitude: guia.lat, longitude: guia.lon },
          ]}
          strokeColor={COLORES.miguel}
          strokeWidth={5}
        />
        <Marker coordinate={{ latitude: guia.lat, longitude: guia.lon }} title={guia.puesto_id} anchor={{ x: 0.5, y: 0.5 }}>
          <View style={estilos.puesto}>
            <Text style={estilos.puestoTexto}>P</Text>
          </View>
        </Marker>
        {destino && (
          <Marker coordinate={{ latitude: destino.lat, longitude: destino.lon }} title={destino.nombre} pinColor={COLORES.gris} />
        )}
        <Marker coordinate={{ latitude: posicion.lat, longitude: posicion.lon }} anchor={{ x: 0.5, y: 0.5 }} zIndex={10}>
          <Text style={estilos.auto}>🚗</Text>
        </Marker>
      </MapView>
      <View style={estilos.panel}>
        <Text style={estilos.estado}>Guiado al puesto</Text>
        <Text style={estilos.distancia}>{distancia !== null ? `${Math.round(distancia)} m` : '--'}</Text>
        <Text style={estilos.detalle} numberOfLines={2}>
          Puesto {guia.puesto_id} · a {Math.round(guia.distancia_m)} m de {destino?.nombre ?? 'tu destino'} · llegas en ~{segundos} s
        </Text>
        <View style={estilos.botones}>
          <Boton
            texto="Cancelar"
            onPress={() => {
              despachar({ tipo: 'REINICIAR' });
              router.replace('/sesion');
            }}
            style={[estilos.boton, estilos.secundario]}
          />
          <Boton
            texto="Llegar ya"
            onPress={() => despachar({ tipo: 'AVANZAR', posicion: { lat: guia.lat, lon: guia.lon } })}
            style={estilos.boton}
          />
        </View>
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  contenedor: { flex: 1 },
  mapa: { flex: 1 },
  auto: { fontSize: 28 },
  puesto: {
    width: 28,
    height: 28,
    borderRadius: 6,
    backgroundColor: COLORES.libre,
    alignItems: 'center',
    justifyContent: 'center',
  },
  puestoTexto: { color: '#fff', fontWeight: '800' },
  panel: { padding: 14, paddingBottom: 28 },
  estado: { fontSize: 22, fontWeight: '800', color: COLORES.miguel },
  distancia: { fontSize: 40, fontWeight: '800', fontVariant: ['tabular-nums'] },
  detalle: { color: COLORES.gris },
  botones: { flexDirection: 'row', gap: 8, backgroundColor: 'transparent' },
  boton: { flex: 1 },
  secundario: { backgroundColor: COLORES.gris },
});
