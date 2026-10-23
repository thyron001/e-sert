import { Stack, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import type { EstadoSesion, MensajeEspejo } from '@/src/api/tipos';
import { BannerAvisos } from '@/src/espejo/componentes/BannerAvisos';
import { CostoVivo } from '@/src/espejo/componentes/CostoVivo';
import { LineaTiempo } from '@/src/espejo/componentes/LineaTiempo';
import { MapaEspejo } from '@/src/espejo/componentes/MapaEspejo';
import { ReciboEspejo } from '@/src/espejo/componentes/ReciboEspejo';
import { NOMBRE_ESTADO, mmss } from '@/src/espejo/formato';
import { suscribirMock } from '@/src/espejo/recorridoMock';
import { esFinEspejo, esMensajeEspejo } from '@/src/espejo/validar';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';

export default function PantallaEspejo() {
  const { vehId } = useLocalSearchParams<{ vehId: string }>();
  const [mensaje, setMensaje] = useState<MensajeEspejo | null>(null);
  const [inicios, setInicios] = useState<Partial<Record<EstadoSesion, number>>>({});
  const [fin, setFin] = useState(false);
  const [verRecibo, setVerRecibo] = useState(false);
  const [ronda, setRonda] = useState(0);

  // MOCK: suscribirMock tiene la misma firma que tendrá el cliente de WS /ws/espejo/{veh_id}.
  useEffect(() => {
    setMensaje(null);
    setInicios({});
    setFin(false);
    setVerRecibo(false);
    let reciboMostrado = false;
    return suscribirMock(vehId, (m) => {
      if (esFinEspejo(m)) return setFin(true);
      if (!esMensajeEspejo(m)) return; // se descartan mensajes malformados
      setMensaje(m);
      if (m.estado) {
        const estado = m.estado;
        setInicios((prev) => (estado in prev ? prev : { ...prev, [estado]: m.t_sim }));
      }
      if (m.recibo && !reciboMostrado) {
        reciboMostrado = true;
        setVerRecibo(true);
      }
    });
  }, [vehId, ronda]);

  // El Modal se dibuja por encima de toda la app: se cierra si la pantalla pierde el foco.
  useFocusEffect(useCallback(() => () => setVerRecibo(false), []));

  const estado = mensaje?.estado ?? null;
  const puesto = mensaje?.puesto;

  return (
    <View style={estilos.contenedor}>
      <Stack.Screen options={{ title: `Espejo · ${vehId}` }} />
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
        {fin && <Text style={estilos.fin}>El vehículo salió de la simulación.</Text>}
        <View style={estilos.botones}>
          {mensaje?.recibo && (
            <Boton texto="Ver recibo" onPress={() => setVerRecibo(true)} style={[estilos.boton, estilos.secundario]} />
          )}
          <Boton texto="Reiniciar recorrido" onPress={() => setRonda((r) => r + 1)} style={estilos.boton} />
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
  botones: { flexDirection: 'row', gap: 8, backgroundColor: 'transparent' },
  boton: { flex: 1 },
  secundario: { backgroundColor: COLORES.libre },
});
