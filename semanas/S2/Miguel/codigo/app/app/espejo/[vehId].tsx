import { Stack, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { BannerAvisos } from '@/src/espejo/componentes/BannerAvisos';
import { CostoVivo } from '@/src/espejo/componentes/CostoVivo';
import { LineaTiempo } from '@/src/espejo/componentes/LineaTiempo';
import { MapaEspejo } from '@/src/espejo/componentes/MapaEspejo';
import { ReciboEspejo } from '@/src/espejo/componentes/ReciboEspejo';
import { NOMBRE_ESTADO, mmss } from '@/src/espejo/formato';
import { IndicadorConexion } from '@/src/espejo/componentes/IndicadorConexion';
import { exportarCSV } from '@/src/espejo/latencia';
import { usarEspejo } from '@/src/espejo/usarEspejo';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';

export default function PantallaEspejo() {
  const { vehId } = useLocalSearchParams<{ vehId: string }>();
  const { mensaje, inicios, fin, conexion, modo, resumen, registro, reiniciar } = usarEspejo(vehId);
  const [verRecibo, setVerRecibo] = useState(false);
  const reciboMostrado = useRef(false);

  // El recibo se abre solo la primera vez que llega en la sesión.
  useEffect(() => {
    if (!mensaje) reciboMostrado.current = false;
    if (mensaje?.recibo && !reciboMostrado.current) {
      reciboMostrado.current = true;
      setVerRecibo(true);
    }
  }, [mensaje]);

  // El Modal se dibuja por encima de toda la app: se cierra si la pantalla pierde el foco.
  useFocusEffect(useCallback(() => () => setVerRecibo(false), []));

  const estado = mensaje?.estado ?? null;
  const puesto = mensaje?.puesto;

  return (
    <View style={estilos.contenedor}>
      <Stack.Screen
        options={{ title: `Espejo · ${vehId}`, headerRight: () => <IndicadorConexion conexion={conexion} /> }}
      />
      <View style={estilos.mapa}>
        <MapaEspejo mensaje={mensaje} />
      </View>
      <View style={estilos.panel}>
        <View style={estilos.cabecera}>
          <Text style={estilos.estado}>{estado ? NOMBRE_ESTADO[estado] : 'Conectando…'}</Text>
          <Text style={estilos.tsim}>t_sim {mensaje ? mmss(mensaje.t_sim) : '--:--'}</Text>
        </View>
        <Text style={estilos.detalle} numberOfLines={1}>
          {mensaje?.destino ? `Destino: ${mensaje.destino.nombre}` : ' '}
          {puesto ? ` · Puesto a ${puesto.distancia_m} m` : ''}
        </Text>
        <BannerAvisos avisos={mensaje?.avisos ?? []} />
        <CostoVivo sesion={mensaje?.sesion ?? null} billetera={mensaje?.billetera ?? null} />
        <View style={estilos.linea}>
          <LineaTiempo actual={estado} inicios={inicios} />
        </View>
        {fin && (
          <Text style={estilos.fin}>
            {fin.motivo === 'no_existe' ? 'Ese vehículo ya no está en la simulación.' : 'El vehículo salió de la simulación.'}
          </Text>
        )}
        {resumen.n > 0 && (
          <Text style={estilos.latencia}>
            Latencia ({modo}, n={resumen.n}): p50 {resumen.total_p50} ms · p95 {resumen.total_p95} ms · en el teléfono p50{' '}
            {resumen.cliente_p50} ms
          </Text>
        )}
        <View style={estilos.botones}>
          {mensaje?.recibo && (
            <Boton texto="Ver recibo" onPress={() => setVerRecibo(true)} style={[estilos.boton, estilos.secundario]} />
          )}
          {fin && resumen.n > 0 && (
            <Boton texto="Exportar CSV" onPress={() => exportarCSV(registro, modo).catch((e) => Alert.alert('No se pudo exportar', String(e)))} style={[estilos.boton, estilos.secundario]} />
          )}
          <Boton texto={modo === 'mock_interno' ? 'Reiniciar recorrido' : 'Reconectar'} onPress={reiniciar} style={estilos.boton} />
        </View>
      </View>
      <ReciboEspejo recibo={mensaje?.recibo ?? null} visible={verRecibo} alCerrar={() => setVerRecibo(false)} />
    </View>
  );
}

const estilos = StyleSheet.create({
  contenedor: { flex: 1 },
  mapa: { flex: 1 },
  panel: { padding: 14, paddingBottom: 24, borderTopLeftRadius: 16, borderTopRightRadius: 16, marginTop: -16 },
  cabecera: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', backgroundColor: 'transparent' },
  estado: { fontSize: 24, fontWeight: '800', color: COLORES.miguel },
  tsim: { color: COLORES.gris, fontVariant: ['tabular-nums'] },
  detalle: { color: COLORES.gris, marginBottom: 8 },
  linea: { marginTop: 12, backgroundColor: 'transparent' },
  fin: { marginTop: 8, color: COLORES.gris, textAlign: 'center' },
  latencia: { marginTop: 6, color: COLORES.gris, fontSize: 12, textAlign: 'center', fontVariant: ['tabular-nums'] },
  botones: { flexDirection: 'row', gap: 8, backgroundColor: 'transparent' },
  boton: { flex: 1 },
  secundario: { backgroundColor: COLORES.libre },
});
