import * as Linking from 'expo-linking';
import { router, useLocalSearchParams } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, TextInput } from 'react-native';

import { Text, View, useThemeColor } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { mensajeUsuario } from '@/src/api/cliente';
import { consultarPago, esperarConfirmacion, leerMonto, MONTOS_RAPIDOS, prepararPago } from '@/src/api/pagos';
import { TARIFA } from '@/src/api/tarifa';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

type Resultado = { tipo: 'exito' | 'error' | 'info'; texto: string };

// Recarga con Payphone (botón de pagos): el backend prepara el pago, la app abre pay_url en el
// navegador del sistema y, al volver por el deep link, consulta el estado de la intención.
// El backend decide si es Payphone en pruebas o su página mock (PAYPHONE_MODO).
export default function Recarga() {
  const { api, usuarioId, urlApi, modoMock } = useAjustes();
  const colorTexto = useThemeColor({}, 'text');
  const [elegido, setElegido] = useState<number>(MONTOS_RAPIDOS[0]);
  const [libre, setLibre] = useState('');
  const [ocupado, setOcupado] = useState(false);
  const [paso, setPaso] = useState<string | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);

  const lectura = libre ? leerMonto(libre) : { monto: elegido };
  const monto = 'monto' in lectura ? lectura.monto : null;
  // Solo en desarrollo: ?monto=<usd>&auto=1 para manejar la pantalla desde la terminal.
  const params = useLocalSearchParams<{ monto?: string; auto?: string }>();
  const [autoListo, setAutoListo] = useState(false);

  useEffect(() => {
    if (__DEV__ && params.monto) setLibre(params.monto);
  }, [params.monto]);

  useEffect(() => {
    if (__DEV__ && params.auto === '1' && !autoListo && libre && monto !== null) {
      setAutoListo(true);
      pagar();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.auto, libre, monto, autoListo]);

  async function pagar() {
    if (monto === null) return;
    setOcupado(true);
    setResultado(null);
    try {
      if (modoMock) {
        // Sin backend (cliente mock de la app): se acredita en la billetera en memoria.
        const r = await api.recargar(usuarioId, { monto, referencia_payphone: 'mock-local' });
        setResultado({ tipo: 'exito', texto: `Recarga de ${usd(monto)} acreditada. Saldo: ${usd(r.saldo)}` });
        return;
      }
      setPaso('Preparando el pago…');
      const urlApp = Linking.createURL('pagos/retorno');
      const pago = await prepararPago(urlApi, usuarioId, monto, urlApp);

      setPaso(pago.modo === 'mock' ? 'Pago simulado (mock) abierto…' : 'Payphone abierto…');
      await WebBrowser.openAuthSessionAsync(pago.pay_url, urlApp);

      // Haya vuelto por el deep link o cerrado el navegador, la verdad la tiene el backend.
      setPaso('Confirmando con el servidor…');
      const intencion = await esperarConfirmacion(() => consultarPago(urlApi, pago.client_transaction_id));
      if (intencion.estado === 'aprobado') {
        setResultado({ tipo: 'exito', texto: `Recarga de ${usd(intencion.monto)} confirmada.` });
      } else if (intencion.estado === 'rechazado') {
        setResultado({ tipo: 'error', texto: 'El pago fue rechazado o cancelado. No se cobró nada.' });
      } else {
        setResultado({
          tipo: 'info',
          texto: 'El pago sigue pendiente. Si pagaste, revisa la billetera en unos minutos.',
        });
      }
    } catch (e) {
      setResultado({ tipo: 'error', texto: mensajeUsuario(e) });
    } finally {
      setPaso(null);
      setOcupado(false);
    }
  }

  return (
    <ScrollView
      contentContainerStyle={estilos.contenedor}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled">
      <Text style={estilos.titulo}>Recarga tu billetera</Text>
      <Text style={estilos.texto}>
        Necesitas saldo disponible para el bloque mínimo antes de buscar puesto. La recarga mínima es{' '}
        {usd(TARIFA.recarga_minima_usd)}.
      </Text>

      <View style={estilos.montos}>
        {MONTOS_RAPIDOS.map((m) => {
          const activo = !libre && elegido === m;
          return (
            <Pressable
              key={m}
              onPress={() => {
                setElegido(m);
                setLibre('');
              }}
              style={[estilos.monto, activo && estilos.montoActivo]}>
              <Text style={[estilos.montoTexto, activo && estilos.montoTextoActivo]}>{usd(m)}</Text>
            </Pressable>
          );
        })}
      </View>
      <Text style={estilos.etiqueta}>Otro monto</Text>
      <TextInput
        style={[estilos.entrada, { color: colorTexto }]}
        value={libre}
        onChangeText={setLibre}
        placeholder={`${TARIFA.recarga_minima_usd.toFixed(2)} o más`}
        placeholderTextColor={COLORES.gris}
        keyboardType="decimal-pad"
        maxLength={7}
      />
      {'error' in lectura && <Text style={estilos.error}>{lectura.error}</Text>}

      <Boton
        texto={monto !== null ? `Pagar ${usd(monto)} con Payphone` : 'Pagar con Payphone'}
        onPress={pagar}
        ocupado={ocupado}
        deshabilitado={monto === null}
      />
      {modoMock && <Text style={estilos.nota}>Modo mock de la app: no se abre Payphone.</Text>}
      {paso && <Text style={estilos.nota}>{paso}</Text>}
      {resultado && (
        <Text style={[estilos.resultado, estilos[resultado.tipo]]}>{resultado.texto}</Text>
      )}
      {resultado?.tipo === 'exito' && <Boton texto="Volver" onPress={() => router.back()} />}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  contenedor: { padding: 16 },
  titulo: { fontSize: 24, fontWeight: '800', color: COLORES.miguel, marginBottom: 8 },
  texto: { marginBottom: 12 },
  montos: { flexDirection: 'row', gap: 10, marginBottom: 12, backgroundColor: 'transparent' },
  monto: {
    flex: 1,
    borderWidth: 1.5,
    borderColor: COLORES.miguel,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  montoActivo: { backgroundColor: COLORES.miguel },
  montoTexto: { fontSize: 18, fontWeight: '700', color: COLORES.miguel },
  montoTextoActivo: { color: '#fff' },
  etiqueta: { fontWeight: '700', marginBottom: 6 },
  entrada: {
    borderWidth: 1,
    borderColor: COLORES.gris,
    borderRadius: 8,
    padding: 10,
    fontSize: 18,
  },
  error: { color: COLORES.lleno, marginTop: 6 },
  nota: { color: COLORES.gris, marginTop: 8 },
  resultado: { marginTop: 12, fontSize: 16, fontWeight: '700' },
  exito: { color: COLORES.libre },
  info: { color: COLORES.gris },
});
