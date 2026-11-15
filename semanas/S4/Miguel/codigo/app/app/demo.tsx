import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, TextInput } from 'react-native';

import { Text, View, useThemeColor } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import {
  guardarIpLocal,
  leerIpLocal,
  probarConexion,
  probarWsEspejo,
  suscribirEstadoEspejo,
  URL_VPS,
  urlLocal,
  type EstadoWsEspejo,
  type Prueba,
} from '@/src/config/demo';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';

const TEXTO_WS: Record<string, string> = {
  en_vivo: 'En vivo',
  reconectando: 'Reconectando',
  sin_conexion: 'Sin conexión',
  finalizado: 'Finalizado',
  mock: 'Mock interno (sin red)',
  cerrado: 'Ningún espejo abierto',
};

// Pantalla oculta (mantener pulsado el logo 3 s): a qué backend apunta la app en la demo.
export default function AjustesDemo() {
  const { urlApi, cambiarUrl, modoMock, cambiarModoMock } = useAjustes();
  const colorTexto = useThemeColor({}, 'text');
  const [borrador, setBorrador] = useState(urlApi);
  const [ip, setIp] = useState('');
  const [probando, setProbando] = useState(false);
  const [resultado, setResultado] = useState<{ salud: Prueba; candidatos: Prueba; ws: Prueba | null } | null>(null);
  const [ws, setWs] = useState<EstadoWsEspejo | null>(null);

  useEffect(() => setBorrador(urlApi), [urlApi]);
  useEffect(() => {
    leerIpLocal().then(setIp);
  }, []);
  useEffect(() => suscribirEstadoEspejo(setWs), []);

  async function usar(url: string) {
    setBorrador(url);
    setResultado(null);
    if (modoMock) await cambiarModoMock(false);
    await cambiarUrl(url);
  }

  async function probar() {
    setProbando(true);
    setResultado(null);
    const r = await probarConexion(borrador);
    const wsPrueba = r.ids.length ? await probarWsEspejo(borrador, r.ids[0]) : null;
    setResultado({ salud: r.salud, candidatos: r.candidatos, ws: wsPrueba });
    setProbando(false);
  }

  return (
    <ScrollView contentContainerStyle={estilos.contenedor} contentInsetAdjustmentBehavior="automatic" keyboardShouldPersistTaps="handled">
      <Text style={estilos.titulo}>Ajustes de demo</Text>
      <Text style={estilos.ayuda}>Se guarda en el teléfono y se aplica al instante, sin reinstalar la app.</Text>

      <Text style={estilos.etiqueta}>Backend en uso</Text>
      <Text style={estilos.actual} selectable>
        {modoMock ? 'Modo mock (sin backend)' : urlApi}
      </Text>

      <Boton texto="VPS (demo.e-sert.tesisucuenca.com)" onPress={() => usar(URL_VPS)} />

      <Text style={estilos.etiqueta}>Local (la IP que imprime demo.py --local)</Text>
      <View style={estilos.fila}>
        <TextInput
          style={[estilos.entrada, { color: colorTexto }]}
          value={ip}
          onChangeText={setIp}
          placeholder="192.168.1.20"
          placeholderTextColor={COLORES.gris}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="numbers-and-punctuation"
          accessibilityLabel="IP de la computadora con el backend local"
        />
        <Boton
          texto="Usar local"
          onPress={() => {
            guardarIpLocal(ip);
            usar(urlLocal(ip));
          }}
          deshabilitado={!ip.trim()}
          style={estilos.botonFila}
        />
      </View>

      <Text style={estilos.etiqueta}>Otra URL</Text>
      <TextInput
        style={[estilos.entrada, { color: colorTexto }]}
        value={borrador}
        onChangeText={setBorrador}
        onEndEditing={() => usar(borrador.trim())}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        accessibilityLabel="URL del backend"
      />

      <Boton texto="Probar conexión" onPress={probar} ocupado={probando} style={estilos.probar} />
      {resultado && (
        <View style={estilos.tarjeta}>
          <Fila nombre="GET /salud" p={resultado.salud} />
          <Fila nombre="GET /api/v1/espejo/candidatos" p={resultado.candidatos} />
          {resultado.ws ? <Fila nombre="WS /ws/espejo" p={resultado.ws} /> : <Text style={estilos.ayuda}>WS: sin autos que seguir ahora.</Text>}
        </View>
      )}

      <Text style={estilos.etiqueta}>WebSocket del espejo</Text>
      <Text style={estilos.actual}>
        {ws ? `${TEXTO_WS[ws.estado] ?? ws.estado}${ws.vehId ? ` · ${ws.vehId}` : ''}` : '…'}
      </Text>
    </ScrollView>
  );
}

function Fila({ nombre, p }: { nombre: string; p: Prueba }) {
  return (
    <View style={estilos.filaPrueba}>
      <Text style={[estilos.icono, { color: p.ok ? COLORES.libre : COLORES.lleno }]}>{p.ok ? '✓' : '✗'}</Text>
      <View style={estilos.textosPrueba}>
        <Text style={estilos.nombrePrueba}>{nombre}</Text>
        <Text style={estilos.ayuda}>
          {p.detalle}
          {p.ms !== null ? ` · ${p.ms} ms` : ''}
        </Text>
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  contenedor: { padding: 16 },
  titulo: { fontSize: 24, fontWeight: '800', color: COLORES.miguel },
  etiqueta: { fontSize: 15, fontWeight: '700', marginTop: 18, marginBottom: 6 },
  ayuda: { color: COLORES.gris, fontSize: 13 },
  actual: { fontFamily: 'SpaceMono', fontSize: 13 },
  fila: { flexDirection: 'row', gap: 8, alignItems: 'center', backgroundColor: 'transparent' },
  entrada: { flex: 1, minHeight: 44, borderWidth: 1, borderColor: COLORES.gris, borderRadius: 8, paddingHorizontal: 10, fontSize: 16 },
  botonFila: { marginTop: 0 },
  probar: { marginTop: 20 },
  tarjeta: { marginTop: 10, padding: 12, borderRadius: 10, borderWidth: StyleSheet.hairlineWidth, borderColor: COLORES.gris, gap: 8 },
  filaPrueba: { flexDirection: 'row', gap: 10, alignItems: 'center', backgroundColor: 'transparent' },
  icono: { fontSize: 20, fontWeight: '800', width: 20 },
  textosPrueba: { flex: 1, backgroundColor: 'transparent' },
  nombrePrueba: { fontWeight: '600' },
});
