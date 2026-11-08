import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Switch, TextInput } from 'react-native';

import { Text, View, useThemeColor } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';

export default function AjustesScreen() {
  const { urlApi, modoMock, usuarioId, api, cambiarUrl, cambiarModoMock } = useAjustes();
  const [borrador, setBorrador] = useState(urlApi);
  const [probando, setProbando] = useState(false);
  const [resultado, setResultado] = useState<string | null>(null);
  const colorTexto = useThemeColor({}, 'text');

  useEffect(() => setBorrador(urlApi), [urlApi]);

  async function probar() {
    setProbando(true);
    setResultado(null);
    const inicio = Date.now();
    try {
      const puestos = await api.listarPuestos();
      setResultado(`OK: ${puestos.length} puestos en ${Date.now() - inicio} ms`);
    } catch (e) {
      setResultado(`Error: ${(e as Error).message}`);
    } finally {
      setProbando(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.contenedor}>
      <Text style={styles.etiqueta}>URL del backend</Text>
      <TextInput
        style={[styles.entrada, { color: colorTexto }]}
        value={borrador}
        onChangeText={setBorrador}
        onEndEditing={() => cambiarUrl(borrador)}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        editable={!modoMock}
      />
      <Text style={styles.ayuda}>
        Por defecto sale de EXPO_PUBLIC_API_URL. Se le añade /api/v1.
      </Text>

      <View style={styles.fila}>
        <Text style={styles.etiqueta}>Modo mock</Text>
        <Switch
          value={modoMock}
          onValueChange={cambiarModoMock}
          trackColor={{ true: COLORES.miguel }}
          thumbColor="#FFFFFF"
        />
      </View>
      <Text style={styles.ayuda}>
        {modoMock
          ? 'Usa un backend falso en memoria: 20 puestos y latencia de 300 ms.'
          : 'Usa el backend real en la URL de arriba.'}
      </Text>

      <Text style={styles.etiqueta}>usuario_id</Text>
      <Text selectable style={styles.mono}>
        {usuarioId || '…'}
      </Text>
      <Text style={styles.ayuda}>Generado una vez con expo-crypto y guardado en expo-secure-store.</Text>

      <Boton texto="Probar conexión" onPress={probar} ocupado={probando} />
      {resultado && <Text style={styles.resultado}>{resultado}</Text>}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  contenedor: { padding: 16 },
  etiqueta: { fontSize: 15, fontWeight: '600', marginTop: 16 },
  entrada: {
    borderWidth: 1,
    borderColor: COLORES.gris,
    borderRadius: 8,
    padding: 10,
    marginTop: 6,
  },
  ayuda: { fontSize: 12, color: COLORES.gris, marginTop: 4 },
  fila: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'transparent',
  },
  mono: { fontFamily: 'SpaceMono', fontSize: 12, marginTop: 6 },
  resultado: { marginTop: 12 },
});
