import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { getBilletera } from '@/src/api/cliente';
import { TARIFA } from '@/src/api/tarifa';
import type { Billetera } from '@/src/api/tipos';
import { estadoBloqueo, type EstadoBloqueo } from '@/src/logica/calcularAvisos';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

/**
 * Lee la billetera cada vez que la pantalla toma el foco (p. ej. al volver de Recarga) y dice si
 * se puede iniciar sesión. Si POST /sesiones responde SESIONES_BLOQUEADAS, confirmar lleva a
 * Recarga y, al volver, esta lectura ya ve el saldo negativo.
 */
export function useBloqueo(): { billetera: Billetera | null; bloqueo: EstadoBloqueo | null; releer: () => void } {
  const { api, usuarioId, cargado } = useAjustes();
  const [billetera, setBilletera] = useState<Billetera | null>(null);
  const releer = useCallback(() => {
    if (!cargado) return;
    getBilletera(usuarioId, api)
      .then(setBilletera)
      .catch(() => setBilletera(null)); // sin red: no se bloquea por adelantado (el backend decide)
  }, [api, usuarioId, cargado]);
  useFocusEffect(releer);
  return { billetera, bloqueo: billetera ? estadoBloqueo(billetera) : null, releer };
}

/** Tarjeta de bloqueo: deuda o falta de disponible, y el botón Recargar (Payphone de S2-2). */
export function Bloqueo({ bloqueo, billetera }: { bloqueo: EstadoBloqueo; billetera: Billetera }) {
  if (!bloqueo.bloqueado) return null;
  const negativo = bloqueo.motivo === 'saldo_negativo';
  return (
    <View style={estilos.tarjeta}>
      <Text style={estilos.titulo}>{negativo ? '🔒 Sesiones bloqueadas' : 'Saldo insuficiente'}</Text>
      {negativo ? (
        <Text style={estilos.texto}>
          Tu saldo es {usd(billetera.saldo)}: debes {usd(bloqueo.deuda)}. No puedes iniciar una sesión hasta recargar.
        </Text>
      ) : (
        <Text style={estilos.texto}>
          Tu disponible ({usd(billetera.disponible)}) no cubre el bloque mínimo de {TARIFA.bloque_minimo_min} min. Recarga
          al menos {usd(TARIFA.recarga_minima_usd)}.
        </Text>
      )}
      <Text style={estilos.sugerencia}>Recarga sugerida: {usd(bloqueo.recargaSugerida)}</Text>
      <Boton texto="Recargar" onPress={() => router.push('/recarga')} />
    </View>
  );
}

const estilos = StyleSheet.create({
  tarjeta: {
    marginTop: 12,
    padding: 14,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: COLORES.lleno,
    backgroundColor: 'rgba(198,40,40,0.08)',
  },
  titulo: { fontSize: 18, fontWeight: '800', color: COLORES.lleno, marginBottom: 6 },
  texto: { marginBottom: 4 },
  sugerencia: { color: COLORES.gris, fontSize: 13 },
});
