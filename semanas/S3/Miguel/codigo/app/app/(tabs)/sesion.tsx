import { router } from 'expo-router';
import { ScrollView, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { rutaDelFlujo, useSesion } from '@/src/estado/sesion';
import { Bloqueo, usarBloqueo } from '@/src/pantallas/Bloqueo';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

// Entrada al flujo de parqueo: buscar → guiar → confirmar → activa. Si hay un flujo en curso
// (también tras reabrir la app), ofrece continuarlo.
export default function SesionScreen() {
  const { modoMock } = useAjustes();
  const { flujo } = useSesion();
  const ruta = rutaDelFlujo(flujo);
  const { billetera, bloqueo } = usarBloqueo();
  const bloqueado = !ruta && !!bloqueo?.bloqueado;

  return (
    <ScrollView contentContainerStyle={styles.contenedor}>
      <Text style={styles.titulo}>Parquear en el Centro</Text>
      <Text style={styles.ayuda}>
        Elige un destino y la app te asigna un puesto SERT libre cerca. El recorrido es simulado: el teléfono no se
        mueve.
      </Text>
      {ruta && flujo.sesion && (
        <View style={styles.tarjeta}>
          <Text style={styles.estado}>{flujo.estado}</Text>
          <Text>
            {flujo.sesion.placa} · {flujo.sesion.puesto_id}
          </Text>
          <Text>Retenido: {usd(flujo.sesion.retenido)}</Text>
        </View>
      )}
      {ruta ? (
        <Boton texto={ruta === '/sesion/guiar' ? 'Continuar el guiado' : 'Ver sesión activa'} onPress={() => router.push(ruta)} />
      ) : (
        <>
          <Boton texto="Buscar puesto" onPress={() => router.push('/buscar')} deshabilitado={bloqueado} />
          {bloqueado && billetera && bloqueo && <Bloqueo bloqueo={bloqueo} billetera={billetera} />}
        </>
      )}
      <Text style={styles.fuente}>{modoMock ? 'Datos: mock (sin backend)' : 'Datos: backend real'}</Text>
      <Boton
        texto="🚗  Modo espejo: seguir a un conductor simulado"
        onPress={() => router.push('/espejo')}
        style={styles.espejo}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  contenedor: { padding: 16 },
  titulo: { fontSize: 24, fontWeight: '800', color: COLORES.miguel },
  ayuda: { color: COLORES.gris, marginVertical: 8 },
  estado: { fontSize: 20, fontWeight: '700', color: COLORES.miguel },
  tarjeta: { marginTop: 8, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: COLORES.gris, gap: 4 },
  fuente: { color: COLORES.gris, fontSize: 12, marginTop: 8, textAlign: 'center' },
  espejo: { backgroundColor: '#1565C0', marginTop: 24 },
});
