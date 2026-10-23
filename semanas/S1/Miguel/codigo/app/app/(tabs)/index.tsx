import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet } from 'react-native';
import MapView, { Circle } from 'react-native-maps';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import type { Puesto } from '@/src/api/tipos';
import { COLORES } from '@/src/ui/colores';

const REGION_INICIAL = {
  latitude: -2.8975, // Parque Calderón
  longitude: -79.0045,
  latitudeDelta: 0.009,
  longitudeDelta: 0.009,
};

export default function MapaScreen() {
  const { api, modoMock, cargado } = useAjustes();
  const [puestos, setPuestos] = useState<Puesto[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setPuestos(await api.listarPuestos());
    } catch (e) {
      setPuestos([]);
      setError((e as Error).message);
    } finally {
      setCargando(false);
    }
  }, [api]);

  useEffect(() => {
    if (cargado) cargar();
  }, [cargado, cargar]);

  const libres = puestos.filter((p) => p.ocupados < p.capacidad).length;

  return (
    <View style={styles.contenedor}>
      <MapView style={StyleSheet.absoluteFill} initialRegion={REGION_INICIAL}>
        {puestos.map((p) => {
          const libre = p.ocupados < p.capacidad;
          const color = libre ? COLORES.libre : COLORES.lleno;
          return (
            <Circle
              key={p.puesto_id}
              center={{ latitude: p.lat, longitude: p.lon }}
              radius={14}
              fillColor={color + 'CC'}
              strokeColor={color}
              strokeWidth={2}
            />
          );
        })}
      </MapView>

      <View style={styles.panel}>
        <Text style={styles.titulo}>
          {libres} con espacio · {puestos.length - libres} llenos
        </Text>
        <View style={styles.fila}>
          <View style={[styles.punto, { backgroundColor: COLORES.libre }]} />
          <Text>libre</Text>
          <View style={[styles.punto, { backgroundColor: COLORES.lleno, marginLeft: 12 }]} />
          <Text>lleno</Text>
          <Text style={styles.modo}>{modoMock ? 'MOCK' : 'API'}</Text>
        </View>
        {error && <Text style={styles.error}>{error}</Text>}
        <Pressable style={styles.boton} onPress={cargar} disabled={cargando}>
          {cargando ? <ActivityIndicator color="#fff" /> : <Text style={styles.textoBoton}>Actualizar</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  contenedor: { flex: 1 },
  panel: {
    position: 'absolute',
    left: 12,
    right: 12,
    bottom: 12,
    padding: 12,
    borderRadius: 12,
    opacity: 0.95,
  },
  titulo: { fontSize: 16, fontWeight: '600', marginBottom: 6 },
  fila: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'transparent' },
  punto: { width: 12, height: 12, borderRadius: 6, marginRight: 4 },
  modo: { marginLeft: 'auto', fontWeight: '700', color: COLORES.miguel },
  error: { color: COLORES.lleno, marginTop: 6 },
  boton: {
    marginTop: 10,
    backgroundColor: COLORES.miguel,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
  },
  textoBoton: { color: '#fff', fontWeight: '600' },
});
