import { router, useLocalSearchParams } from 'expo-router';
import { useMemo } from 'react';
import { ScrollView } from 'react-native';

import { Text } from '@/components/Themed';
import { useSesion } from '@/src/estado/sesion';
import { Recibo } from '@/src/pantallas/Recibo';
import type { MensajeEspejo } from '@/src/api/tipos';
import { generarRecorridoCierre } from '@/src/mocks/cierreMock';
import { DetectorCierre, type DatosRecibo } from '@/src/servicios/seguimientoSesion';

function reciboDemo(): DatosRecibo | null {
  const detector = new DetectorCierre({ origen: 'espejo', veh_id: 'sim_veh42' });
  for (const m of generarRecorridoCierre('sim_veh42')) {
    if (m.tipo !== 'espejo') continue;
    const ev = detector.mensaje({ ...(m as MensajeEspejo), ts: new Date().toISOString() });
    if (ev?.tipo === 'cierre') return ev.datos;
  }
  return null;
}

// Se llega con router.replace (la sesión activa no queda en el historial) y con los datos del
// cierre en el parámetro `datos` (JSON).
export default function RutaRecibo() {
  // Solo en desarrollo: ?demo=mock arma el recibo pasando el recorrido de cierreMock por el mismo
  // DetectorCierre de la app (simctl no puede tocar la pantalla para llegar hasta aquí).
  const { datos, demo } = useLocalSearchParams<{ datos?: string; demo?: string }>();
  const { despachar } = useSesion();
  const recibo = useMemo<DatosRecibo | null>(() => {
    if (__DEV__ && demo === 'mock') return reciboDemo();
    try {
      return datos ? (JSON.parse(datos) as DatosRecibo) : null;
    } catch {
      return null;
    }
  }, [datos, demo]);

  if (!recibo) {
    return (
      <ScrollView contentContainerStyle={{ padding: 16 }} contentInsetAdjustmentBehavior="automatic">
        <Text>No hay recibo para mostrar.</Text>
      </ScrollView>
    );
  }

  return (
    <Recibo
      datos={recibo}
      alTerminar={() => {
        if (recibo.origen === 'propia') despachar({ tipo: 'REINICIAR' });
        router.replace(recibo.origen === 'espejo' ? '/espejo' : '/sesion');
      }}
    />
  );
}
