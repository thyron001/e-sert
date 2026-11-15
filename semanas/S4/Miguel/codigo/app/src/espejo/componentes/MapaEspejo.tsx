import { useEffect, useRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import MapView, { Marker, Polyline } from 'react-native-maps';

import type { MensajeEspejo } from '@/src/api/tipos';
import { COLORES } from '@/src/ui/colores';
import { rumbo } from '../formato';

const ZOOM_AUTO = 0.007;
const ZOOM_A_PIE = 0.003;

/** Mapa del conductor espejo: auto (rota con el rumbo), destino, puesto y la ruta de guiado. */
export function MapaEspejo({ mensaje }: { mensaje: MensajeEspejo | null }) {
  const mapa = useRef<MapView>(null);
  const anterior = useRef<[number, number] | null>(null);
  const angulo = useRef(0);

  const posicion: [number, number] | null = mensaje ? [mensaje.lat, mensaje.lon] : null;
  if (posicion && anterior.current) {
    const [a, b] = [anterior.current, posicion];
    if (a[0] !== b[0] || a[1] !== b[1]) angulo.current = rumbo(a, b);
  }
  const caminando = mensaje?.estado === 'A_PIE' || mensaje?.estado === 'REGRESANDO';

  useEffect(() => {
    if (!mensaje) return;
    anterior.current = [mensaje.lat, mensaje.lon];
    const zoom = caminando || mensaje.estado === 'ESTACIONADO' ? ZOOM_A_PIE : ZOOM_AUTO;
    mapa.current?.animateToRegion(
      { latitude: mensaje.lat, longitude: mensaje.lon, latitudeDelta: zoom, longitudeDelta: zoom },
      800,
    );
  }, [mensaje, caminando]);

  return (
    <MapView
      ref={mapa}
      style={StyleSheet.absoluteFill}
      initialRegion={{ latitude: -2.8975, longitude: -79.0045, latitudeDelta: 0.012, longitudeDelta: 0.012 }}>
      {mensaje && mensaje.ruta.length > 1 && (
        <Polyline
          coordinates={mensaje.ruta.map(([lat, lon]) => ({ latitude: lat, longitude: lon }))}
          strokeColor="#1565C0"
          strokeWidth={5}
        />
      )}
      {mensaje?.destino && (
        <Marker
          coordinate={{ latitude: mensaje.destino.lat, longitude: mensaje.destino.lon }}
          title={mensaje.destino.nombre}
          pinColor="#1565C0"
        />
      )}
      {mensaje?.puesto && (
        <Marker
          coordinate={{ latitude: mensaje.puesto.lat, longitude: mensaje.puesto.lon }}
          title="Puesto asignado"
          description={mensaje.puesto.puesto_id}
          anchor={{ x: 0.5, y: 0.5 }}
          tracksViewChanges={false}>
          <View style={[estilos.icono, { backgroundColor: COLORES.libre }]}>
            <Text style={estilos.letra}>P</Text>
          </View>
        </Marker>
      )}
      {posicion && (
        <Marker
          coordinate={{ latitude: posicion[0], longitude: posicion[1] }}
          anchor={{ x: 0.5, y: 0.5 }}
          title={mensaje!.veh_id}
          zIndex={10}
          tracksViewChanges>
          {caminando ? (
            <View style={[estilos.icono, { backgroundColor: '#EF6C00' }]}>
              <Text style={estilos.emoji}>🚶</Text>
            </View>
          ) : (
            <View style={[estilos.auto, { transform: [{ rotate: `${angulo.current}deg` }] }]}>
              <Text style={estilos.flecha}>▲</Text>
            </View>
          )}
        </Marker>
      )}
    </MapView>
  );
}

const estilos = StyleSheet.create({
  icono: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#fff',
  },
  letra: { color: '#fff', fontWeight: '800' },
  emoji: { fontSize: 16 },
  auto: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: COLORES.miguel,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 3,
    borderColor: '#fff',
  },
  flecha: { color: '#fff', fontSize: 16, fontWeight: '900', marginTop: -2 },
});
