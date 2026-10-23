import { useCallback, useState } from 'react';
import { ScrollView, StyleSheet, TextInput } from 'react-native';
import { router, useFocusEffect } from 'expo-router';

import { Text, View, useThemeColor } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import type { Sesion } from '@/src/api/tipos';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

// Pantalla base: permite abrir y cerrar una sesión a mano contra la API (o el mock).
// La detección automática de la salida y el modo espejo llegan en sesiones posteriores.
export default function SesionScreen() {
  const { api, usuarioId, cargado } = useAjustes();
  const colorTexto = useThemeColor({}, 'text');
  const [placa, setPlaca] = useState('ABC-1234');
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const refrescar = useCallback(async () => {
    if (sesion) setSesion(await api.obtenerSesion(sesion.sesion_id).catch(() => sesion));
  }, [api, sesion]);

  useFocusEffect(
    useCallback(() => {
      refrescar();
    }, [refrescar]),
  );

  async function ejecutar(accion: () => Promise<void>) {
    setOcupado(true);
    setMensaje(null);
    try {
      await accion();
    } catch (e) {
      setMensaje((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  const iniciar = () =>
    ejecutar(async () => {
      // Sin guiado todavía: toma el primer puesto con espacio.
      const libre = (await api.listarPuestos()).find((p) => p.ocupados < p.capacidad);
      if (!libre) throw new Error('No hay puestos libres');
      const creada = await api.crearSesion({ usuario_id: usuarioId, placa, puesto_id: libre.puesto_id });
      setSesion(await api.obtenerSesion(creada.sesion_id));
      setMensaje(`Retenido ${usd(creada.retenido)} en ${libre.calle}`);
    });

  const cerrar = () =>
    ejecutar(async () => {
      if (!sesion) return;
      const r = await api.cerrarSesion(sesion.sesion_id, { ts: new Date().toISOString(), motivo: 'manual' });
      setSesion(await api.obtenerSesion(sesion.sesion_id));
      setMensaje(`Cobrado ${usd(r.debitado)} por ${r.minutos_cobrados} min`);
    });

  const activa = sesion && sesion.estado !== 'CERRADA';

  return (
    <ScrollView contentContainerStyle={styles.contenedor}>
      <Boton
        texto="🚗  Modo espejo: seguir a un conductor simulado"
        onPress={() => router.push('/espejo')}
        style={styles.espejo}
      />
      <Text style={styles.estado}>{sesion ? sesion.estado : 'Sin sesión'}</Text>
      {sesion && (
        <View style={styles.tarjeta}>
          <Text>Placa: {sesion.placa}</Text>
          <Text>Puesto: {sesion.puesto_id}</Text>
          <Text>Inicio: {new Date(sesion.inicio).toLocaleTimeString()}</Text>
          <Text>Retenido: {usd(sesion.retenido)}</Text>
          {sesion.debitado !== null && (
            <Text>
              Cobrado: {usd(sesion.debitado)} ({sesion.minutos_cobrados} min)
            </Text>
          )}
        </View>
      )}
      {!activa && (
        <>
          <Text style={styles.etiqueta}>Placa</Text>
          <TextInput
            style={[styles.entrada, { color: colorTexto }]}
            value={placa}
            onChangeText={setPlaca}
            autoCapitalize="characters"
          />
          <Boton texto="Confirmar llegada" onPress={iniciar} ocupado={ocupado} deshabilitado={!cargado} />
        </>
      )}
      {activa && <Boton texto="Cerrar sesión (manual)" onPress={cerrar} ocupado={ocupado} />}
      {mensaje && <Text style={styles.mensaje}>{mensaje}</Text>}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  contenedor: { padding: 16 },
  espejo: { backgroundColor: '#1565C0', marginTop: 0, marginBottom: 16 },
  estado: { fontSize: 24, fontWeight: '700', color: COLORES.miguel },
  tarjeta: { marginTop: 12, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: COLORES.gris, gap: 4 },
  etiqueta: { fontSize: 15, fontWeight: '600', marginTop: 16 },
  entrada: { borderWidth: 1, borderColor: COLORES.gris, borderRadius: 8, padding: 10, marginTop: 6 },
  mensaje: { marginTop: 12 },
});
