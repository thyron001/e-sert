import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView, StyleSheet } from 'react-native';

import { Text } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { mensajeUsuario } from '@/src/api/cliente';
import { TARIFA } from '@/src/api/tarifa';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

// La recarga con Payphone es de S2-2. Por ahora: "Próximamente" y, para probar el flujo contra el
// backend real (donde toda billetera empieza en $0), una recarga de prueba sin pago.
export default function Recarga() {
  const { api, usuarioId } = useAjustes();
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);

  async function recargaPrueba() {
    setOcupado(true);
    setMensaje(null);
    try {
      const r = await api.recargar(usuarioId, { monto: TARIFA.recarga_minima_usd });
      setMensaje(`Saldo: ${usd(r.saldo)}`);
      router.back();
    } catch (e) {
      setMensaje(mensajeUsuario(e));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={estilos.contenedor} contentInsetAdjustmentBehavior="automatic">
      <Text style={estilos.titulo}>Recarga tu billetera</Text>
      <Text style={estilos.texto}>
        Necesitas saldo disponible para el bloque mínimo antes de buscar puesto. Recarga al menos{' '}
        {usd(TARIFA.recarga_minima_usd)}.
      </Text>
      <Text style={estilos.proximo}>Recarga con Payphone: próximamente.</Text>
      <Boton
        texto={`Recarga de prueba ${usd(TARIFA.recarga_minima_usd)} (sin pago)`}
        onPress={recargaPrueba}
        ocupado={ocupado}
      />
      {mensaje && <Text style={estilos.mensaje}>{mensaje}</Text>}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  contenedor: { padding: 16 },
  titulo: { fontSize: 24, fontWeight: '800', color: COLORES.miguel, marginBottom: 8 },
  texto: { marginBottom: 12 },
  proximo: { fontSize: 18, fontWeight: '700', marginVertical: 12 },
  mensaje: { marginTop: 8, color: COLORES.gris },
});
