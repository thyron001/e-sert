import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, TextInput } from 'react-native';

import { Text, View, useThemeColor } from '@/components/Themed';
import { interpretarTexto, type Interpretacion } from '@/src/api/asistente';
import type { Destino } from '@/src/api/tipos';
import { DESTINOS } from '@/src/datos/destinos';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';

export const DURACIONES = [10, 15, 30, 45, 60, 90, 120] as const;

type Paso =
  | { tipo: 'escribir' }
  | { tipo: 'confirmar'; destino: Destino; duracion: number; resultado: Interpretacion }
  | { tipo: 'formulario'; motivo: string | null };

/** El destino del asistente es uno de destinos.csv: se usa el mismo objeto de la app si existe. */
function destinoDeLaApp(d: NonNullable<Interpretacion['destino']>): Destino {
  return DESTINOS.find((x) => x.nombre === d.nombre) ?? { nombre: d.nombre, lat: d.lat, lon: d.lon };
}

/**
 * Entrada por lenguaje natural ("cerca de la Catedral Nueva una hora") con confirmación, y el
 * formulario (destino + duración de 10 a 120 min) como alternativa siempre disponible: si el
 * asistente no responde o falta algo, se abre el formulario con lo que sí entendió.
 */
export function EntradaNatural({
  urlBase,
  destinoInicial,
  alBuscar,
  ocupado = false,
}: {
  urlBase: string;
  destinoInicial: Destino;
  alBuscar: (destino: Destino, duracionMin: number) => void;
  ocupado?: boolean;
}) {
  const colorTexto = useThemeColor({}, 'text');
  const [texto, setTexto] = useState('');
  const [cargando, setCargando] = useState(false);
  const [paso, setPaso] = useState<Paso>({ tipo: 'escribir' });
  const [destino, setDestino] = useState<Destino>(destinoInicial);
  const [duracion, setDuracion] = useState<number>(60);
  const [avisos, setAvisos] = useState<string[]>([]);

  async function interpretar() {
    if (!texto.trim()) return;
    setCargando(true);
    setAvisos([]);
    try {
      const r = await interpretarTexto(texto.trim(), urlBase);
      setAvisos(r.avisos ?? []);
      // Lo que no se entendió vuelve al valor inicial: nada de restos de la frase anterior.
      setDestino(r.destino ? destinoDeLaApp(r.destino) : destinoInicial);
      setDuracion(r.duracion_min ?? 60);
      if (r.destino && r.duracion_min) {
        setPaso({ tipo: 'confirmar', destino: destinoDeLaApp(r.destino), duracion: r.duracion_min, resultado: r });
      } else {
        const falta = !r.destino && !r.duracion_min ? 'el destino y la duración' : !r.destino ? 'el destino' : 'la duración';
        setPaso({ tipo: 'formulario', motivo: `No entendí ${falta}. Elígelo aquí.` });
      }
    } catch {
      // Sin asistente (red, servidor o tiempo): la app sigue con el formulario.
      setDestino(destinoInicial);
      setDuracion(60);
      setPaso({ tipo: 'formulario', motivo: 'El asistente no está disponible: elige destino y duración.' });
    } finally {
      setCargando(false);
    }
  }

  if (paso.tipo === 'confirmar') {
    return (
      <View style={estilos.tarjeta}>
        <Text style={estilos.confirmacion}>
          {paso.destino.nombre} · {paso.duracion} min. ¿Correcto?
        </Text>
        <Text style={estilos.fuente}>
          Interpretado por {paso.resultado.fuente === 'llm' ? 'IA (Claude)' : 'reglas'} · confianza{' '}
          {Math.round(paso.resultado.confianza * 100)} %
        </Text>
        {avisos.map((a) => (
          <Text key={a} style={estilos.aviso}>
            ⚠️ {a}
          </Text>
        ))}
        <View style={estilos.fila}>
          <Boton texto="Editar" onPress={() => setPaso({ tipo: 'formulario', motivo: null })} style={[estilos.mitad, estilos.secundario]} />
          <Boton texto="Buscar" onPress={() => alBuscar(paso.destino, paso.duracion)} ocupado={ocupado} style={estilos.mitad} />
        </View>
      </View>
    );
  }

  if (paso.tipo === 'formulario') {
    return (
      <View style={estilos.tarjeta}>
        {paso.motivo && <Text style={estilos.aviso}>{paso.motivo}</Text>}
        {avisos.map((a) => (
          <Text key={a} style={estilos.aviso}>
            ⚠️ {a}
          </Text>
        ))}
        <Text style={estilos.etiqueta}>Destino</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={estilos.chips}>
          {DESTINOS.map((d) => (
            <Chip key={d.nombre} texto={d.nombre} activo={d.nombre === destino.nombre} onPress={() => setDestino(d)} />
          ))}
        </ScrollView>
        <Text style={estilos.etiqueta}>Duración</Text>
        <View style={estilos.chipsFila}>
          {DURACIONES.map((m) => (
            <Chip key={m} texto={`${m} min`} activo={m === duracion} onPress={() => setDuracion(m)} />
          ))}
        </View>
        <View style={estilos.fila}>
          <Boton texto="Escribir de nuevo" onPress={() => setPaso({ tipo: 'escribir' })} style={[estilos.mitad, estilos.secundario]} />
          <Boton texto="Buscar" onPress={() => alBuscar(destino, duracion)} ocupado={ocupado} style={estilos.mitad} />
        </View>
      </View>
    );
  }

  return (
    <View style={estilos.tarjeta}>
      <Text style={estilos.etiqueta}>¿A dónde vas y por cuánto tiempo?</Text>
      <View style={estilos.fila}>
        <TextInput
          style={[estilos.entrada, { color: colorTexto }]}
          value={texto}
          onChangeText={setTexto}
          placeholder="cerca de la Catedral Nueva una hora"
          placeholderTextColor={COLORES.gris}
          returnKeyType="send"
          onSubmitEditing={interpretar}
          maxLength={300}
          accessibilityLabel="Destino y duración en tus palabras"
        />
        <Pressable
          style={[estilos.enviar, (!texto.trim() || cargando) && estilos.inactivo]}
          onPress={interpretar}
          disabled={!texto.trim() || cargando}
          accessibilityRole="button"
          accessibilityLabel="Interpretar">
          {cargando ? <ActivityIndicator color="#fff" /> : <Text style={estilos.enviarTexto}>→</Text>}
        </Pressable>
      </View>
      <Pressable onPress={() => setPaso({ tipo: 'formulario', motivo: null })} accessibilityRole="button" hitSlop={8}>
        <Text style={estilos.enlace}>Prefiero elegir en un formulario</Text>
      </Pressable>
    </View>
  );
}

function Chip({ texto, activo, onPress }: { texto: string; activo: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      style={[estilos.chip, activo && estilos.chipActivo]}
      accessibilityRole="button"
      accessibilityState={{ selected: activo }}>
      <Text style={[estilos.chipTexto, activo && estilos.chipTextoActivo]}>{texto}</Text>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  tarjeta: { marginBottom: 8, backgroundColor: 'transparent' },
  etiqueta: { fontWeight: '700', marginBottom: 6, marginTop: 4 },
  fila: { flexDirection: 'row', gap: 8, alignItems: 'center', backgroundColor: 'transparent' },
  entrada: {
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderColor: COLORES.gris,
    borderRadius: 8,
    paddingHorizontal: 10,
    fontSize: 16,
  },
  enviar: {
    width: 48,
    height: 44,
    borderRadius: 8,
    backgroundColor: COLORES.miguel,
    alignItems: 'center',
    justifyContent: 'center',
  },
  enviarTexto: { color: '#fff', fontSize: 22, fontWeight: '800' },
  inactivo: { opacity: 0.5 },
  enlace: { color: '#1565C0', fontSize: 15, textDecorationLine: 'underline', paddingVertical: 12 },
  confirmacion: { fontSize: 18, fontWeight: '800', marginBottom: 2 },
  fuente: { color: COLORES.gris, fontSize: 12, marginBottom: 4 },
  aviso: { color: '#8D6E00', marginVertical: 2 },
  mitad: { flex: 1 },
  secundario: { backgroundColor: COLORES.gris },
  chips: { gap: 8, paddingBottom: 4 },
  chipsFila: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, backgroundColor: 'transparent' },
  chip: {
    minHeight: 44, // objetivo táctil de al menos 44 pt
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: COLORES.gris,
    borderRadius: 18,
    paddingHorizontal: 12,
  },
  chipActivo: { backgroundColor: COLORES.miguel, borderColor: COLORES.miguel },
  chipTexto: { fontSize: 13 },
  chipTextoActivo: { color: '#fff', fontWeight: '700' },
});
