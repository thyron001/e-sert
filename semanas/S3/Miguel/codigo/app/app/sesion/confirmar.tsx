import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, TextInput } from 'react-native';

import { Text, View, useThemeColor } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { crearSesion, getBilletera, mensajeUsuario } from '@/src/api/cliente';
import { programarAvisos } from '@/src/servicios/avisos';
import { montoRetencion, TARIFA } from '@/src/api/tarifa';
import { ErrorApi } from '@/src/api/tipos';
import { useSesion } from '@/src/estado/sesion';
import { esPlacaValida, normalizarPlaca } from '@/src/sesion/placa';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

// Llegada: el usuario confirma placa y puesto; POST /sesiones retiene el bloque mínimo.
export default function Confirmar() {
  const { api, usuarioId } = useAjustes();
  const { flujo, despachar } = useSesion();
  const colorTexto = useThemeColor({}, 'text');
  const [placa, setPlaca] = useState(flujo.ultimaPlaca);
  const [puesto, setPuesto] = useState(flujo.guia?.puesto_id ?? '');
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Solo en desarrollo: ?placa=ABC-1234&auto=1 llena la placa y confirma desde la terminal.
  const params = useLocalSearchParams<{ placa?: string; auto?: string }>();

  useEffect(() => {
    if (!__DEV__ || !params.placa) return;
    setPlaca(normalizarPlaca(params.placa));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.placa]);

  const placaValida = esPlacaValida(placa);
  const puestoValido = puesto.trim().length > 0;

  useEffect(() => {
    if (__DEV__ && params.auto === '1' && placaValida && puestoValido) confirmar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.auto, placaValida]);

  async function confirmar() {
    setOcupado(true);
    setError(null);
    try {
      // Se envía el ts del teléfono: así el cronómetro y el cobro del backend parten del mismo instante.
      const ts = new Date().toISOString();
      const creada = await crearSesion({ usuario_id: usuarioId, placa, puesto_id: puesto.trim(), ts }, api);
      despachar({
        tipo: 'SESION_CREADA',
        sesion: { sesion_id: creada.sesion_id, placa, puesto_id: puesto.trim(), inicio: ts, retenido: creada.retenido },
      });
      // Avisos de saldo bajo y tope SERT programados desde la llegada (S3-2). Se espera a tenerlos
      // antes de navegar, para que un cierre inmediato los encuentre y los cancele.
      try {
        const b = await getBilletera(usuarioId, api);
        await programarAvisos({ sesion_id: creada.sesion_id, inicio: ts }, b);
      } catch (e) {
        console.warn('[avisos] no se pudieron programar', e); // sin billetera, sin avisos
      }
      router.replace('/sesion/activa');
    } catch (e) {
      setError(mensajeUsuario(e));
      // Sin disponible para la retención (o saldo negativo): directo a recargar.
      if (e instanceof ErrorApi && (e.codigo === 'SALDO_INSUFICIENTE' || e.codigo === 'SESIONES_BLOQUEADAS')) {
        router.push('/recarga');
      }
    } finally {
      setOcupado(false);
    }
  }

  return (
    <ScrollView
      contentContainerStyle={estilos.contenedor}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled">
      <Text style={estilos.titulo}>Llegaste al puesto</Text>
      <Text style={estilos.ayuda}>Confirma tu placa y el puesto para iniciar la sesión.</Text>

      <Text style={estilos.etiqueta}>Placa</Text>
      <TextInput
        style={[estilos.entrada, { color: colorTexto }, placa.length > 0 && !placaValida && estilos.entradaMala]}
        value={placa}
        onChangeText={(t) => setPlaca(normalizarPlaca(t))}
        autoCapitalize="characters"
        autoCorrect={false}
        placeholder="ABC-1234"
        placeholderTextColor={COLORES.gris}
        maxLength={8}
      />
      {placa.length > 0 && !placaValida && (
        <Text style={estilos.error}>Formato ecuatoriano: 3 letras y 3 o 4 números (ABC-1234).</Text>
      )}

      <Text style={estilos.etiqueta}>Puesto</Text>
      <TextInput
        style={[estilos.entrada, { color: colorTexto }]}
        value={puesto}
        onChangeText={setPuesto}
        autoCapitalize="none"
        autoCorrect={false}
      />

      <View style={estilos.tarjeta}>
        <Text>
          Al confirmar se retienen {usd(montoRetencion())} ({TARIFA.bloque_minimo_min} min). Al salir se cobra el
          tiempo real en fracciones de {TARIFA.fraccion_min} min (mínimo {TARIFA.cobro_minimo_min} min) y se libera
          la retención.
        </Text>
      </View>

      {error && <Text style={estilos.error}>{error}</Text>}
      <Boton texto="Confirmar e iniciar" onPress={confirmar} ocupado={ocupado} deshabilitado={!placaValida || !puestoValido} />
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  contenedor: { padding: 16 },
  titulo: { fontSize: 24, fontWeight: '800', color: COLORES.miguel },
  ayuda: { color: COLORES.gris, marginBottom: 12 },
  etiqueta: { fontWeight: '700', marginTop: 12, marginBottom: 4 },
  entrada: {
    borderWidth: 1,
    borderColor: COLORES.gris,
    borderRadius: 8,
    padding: 12,
    fontSize: 18,
    letterSpacing: 1,
  },
  entradaMala: { borderColor: COLORES.lleno },
  tarjeta: { marginTop: 16, padding: 12, borderRadius: 8, borderWidth: StyleSheet.hairlineWidth, borderColor: COLORES.gris },
  error: { color: COLORES.lleno, marginTop: 6 },
});
