import { File } from 'expo-file-system';
import { useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Platform, Pressable, ScrollView, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import {
  ETIQUETAS,
  PERSONAS,
  compartir,
  esEtiquetaVehiculo,
  listarGrabaciones,
  type Etiqueta,
  type Persona,
  type Telefono,
} from '@/src/sensores/exportar';
import { Grabador, type EstadoGrabacion } from '@/src/sensores/grabador';
import { COLORES } from '@/src/ui/colores';
import { Boton } from '@/src/ui/comunes';

const NOMBRE_ETIQUETA: Record<Etiqueta, string> = {
  a_pie: 'A pie',
  quieto: 'Quieto',
  vehiculo: 'Vehículo',
  vehiculo_lento: 'Vehículo lento',
};

const COLOR_ETIQUETA: Record<Etiqueta, string> = {
  a_pie: '#2E7D32',
  quieto: '#757575',
  vehiculo: '#1565C0',
  vehiculo_lento: '#EF6C00',
};

function duracion(segundos: number): string {
  const s = Math.max(0, Math.floor(segundos));
  const d2 = (n: number) => String(n).padStart(2, '0');
  return `${d2(Math.floor(s / 3600))}:${d2(Math.floor((s % 3600) / 60))}:${d2(s % 60)}`;
}

function Opciones<T extends string>({
  valores,
  valor,
  alElegir,
  etiqueta = (v) => v,
  color = () => COLORES.miguel,
  deshabilitado = false,
}: {
  valores: readonly T[];
  valor: T;
  alElegir: (v: T) => void;
  etiqueta?: (v: T) => string;
  color?: (v: T) => string;
  deshabilitado?: boolean;
}) {
  return (
    <View style={styles.opciones}>
      {valores.map((v) => {
        const activo = v === valor;
        return (
          <Pressable
            key={v}
            onPress={() => alElegir(v)}
            disabled={deshabilitado}
            style={[
              styles.opcion,
              { borderColor: color(v) },
              activo && { backgroundColor: color(v) },
              deshabilitado && !activo && styles.inactivo,
            ]}>
            <Text style={[styles.textoOpcion, activo && styles.textoOpcionActiva]}>{etiqueta(v)}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function GrabadorScreen() {
  const [persona, setPersona] = useState<Persona>('Miguel');
  const [telefono, setTelefono] = useState<Telefono>(Platform.OS === 'ios' ? 'ios' : 'android');
  const [etiqueta, setEtiqueta] = useState<Etiqueta>('a_pie');
  const [estado, setEstado] = useState<EstadoGrabacion | null>(null);
  const [ahora, setAhora] = useState(Date.now() / 1000);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guardadas, setGuardadas] = useState<string[]>([]);
  const grabador = useRef<Grabador | null>(null);
  if (!grabador.current) grabador.current = new Grabador(setEstado);

  const grabando = estado?.grabando ?? false;

  const refrescarLista = useCallback(() => {
    try {
      setGuardadas(listarGrabaciones().map((f) => f.uri));
    } catch {
      setGuardadas([]);
    }
  }, []);

  useFocusEffect(refrescarLista);

  // Reloj de la duración, solo mientras se graba.
  useEffect(() => {
    if (!grabando) return;
    const id = setInterval(() => setAhora(Date.now() / 1000), 1000);
    return () => clearInterval(id);
  }, [grabando]);

  const iniciar = useCallback(
    async (p: Persona = persona, tel: Telefono = telefono, et: Etiqueta = etiqueta) => {
      setOcupado(true);
      setError(null);
      try {
        await grabador.current!.iniciar(p, tel, et);
        setAhora(Date.now() / 1000);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setOcupado(false);
      }
    },
    [persona, telefono, etiqueta],
  );

  const detener = useCallback(async () => {
    setOcupado(true);
    try {
      await grabador.current!.detener();
      refrescarLista();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }, [refrescarLista]);

  const elegirEtiqueta = useCallback(
    (e: Etiqueta) => {
      setEtiqueta(e);
      const enCaliente = grabador.current!.estado?.grabando ?? false;
      grabador.current!.cambiarEtiqueta(e);
      // Al cambiar en caliente no se interrumpe con un diálogo: basta el aviso fijo en pantalla.
      if (esEtiquetaVehiculo(e) && !enCaliente && Platform.OS !== 'web') {
        Alert.alert('Graba el acompañante', 'Las etiquetas de vehículo las graba siempre el acompañante, nunca quien maneja.');
      }
    },
    [],
  );

  // Solo en desarrollo: permite manejar la grabación por deep link desde el simulador, por ejemplo
  // exp://<ip>:8081/--/grabador?accion=iniciar&etiqueta=a_pie  (accion = iniciar | etiqueta | detener).
  const params = useLocalSearchParams<{ accion?: string; etiqueta?: string; n?: string }>();
  useEffect(() => {
    if (!__DEV__ || !params.accion) return;
    const et = ETIQUETAS.find((x) => x === params.etiqueta);
    if (params.accion === 'iniciar') iniciar(persona, telefono, et ?? etiqueta);
    else if (params.accion === 'etiqueta' && et) {
      setEtiqueta(et);
      grabador.current!.cambiarEtiqueta(et);
    } else if (params.accion === 'detener') detener();
    // `n` hace que dos enlaces iguales seguidos se distingan.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.accion, params.etiqueta, params.n]);

  async function compartirUri(uri: string) {
    try {
      await compartir(new File(uri));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const etiquetaActual = estado?.grabando ? estado.etiqueta : etiqueta;

  return (
    <ScrollView contentContainerStyle={styles.contenedor}>
      <Text style={styles.seccion}>Quién graba</Text>
      <Opciones valores={PERSONAS} valor={persona} alElegir={setPersona} deshabilitado={grabando} />
      <Text style={styles.seccion}>Teléfono</Text>
      <Opciones
        valores={['ios', 'android'] as const}
        valor={telefono}
        alElegir={setTelefono}
        etiqueta={(v) => (v === 'ios' ? 'iOS' : 'Android')}
        deshabilitado={grabando}
      />

      <Text style={styles.seccion}>Etiqueta {grabando && '(se puede cambiar grabando)'}</Text>
      <Opciones
        valores={ETIQUETAS}
        valor={etiquetaActual}
        alElegir={elegirEtiqueta}
        etiqueta={(v) => NOMBRE_ETIQUETA[v]}
        color={(v) => COLOR_ETIQUETA[v]}
      />
      {esEtiquetaVehiculo(etiquetaActual) && (
        <Text style={styles.aviso}>⚠️ Graba el acompañante, nunca quien maneja.</Text>
      )}
      {etiquetaActual === 'vehiculo_lento' && (
        <Text style={styles.ayuda}>Se exporta como modo_real=vehiculo con escenario=trafico_lento.</Text>
      )}

      {grabando ? (
        <Boton texto="■  Detener" onPress={detener} ocupado={ocupado} style={styles.botonGrande} />
      ) : (
        <Boton texto="●  Iniciar" onPress={() => iniciar()} ocupado={ocupado} style={styles.botonGrande} />
      )}
      {error && <Text style={styles.error}>{error}</Text>}

      {estado && (
        <View style={styles.tarjeta}>
          <Text style={styles.grande}>{duracion(ahora - estado.inicio)}</Text>
          <Text>
            GPS: {estado.muestrasGPS} muestras · Acelerómetro:{' '}
            {estado.acelerometro ? `${estado.muestrasAcel} muestras` : 'no disponible'}
          </Text>
          <Text>
            Precisión: {estado.precisionActual == null ? '—' : `${estado.precisionActual.toFixed(0)} m`} · Velocidad:{' '}
            {estado.velocidadActual == null ? '—' : `${(estado.velocidadActual * 3.6).toFixed(1)} km/h`}
          </Text>
          <Text style={styles.ayuda}>
            {estado.usuario_id} · {estado.base}.csv
          </Text>
          <Text style={styles.subtitulo}>Cambios de etiqueta</Text>
          {estado.cambios.map((c, i) => (
            <Text key={i} style={styles.ayuda}>
              +{duracion(c.t - estado.inicio)} → {NOMBRE_ETIQUETA[c.etiqueta]}
            </Text>
          ))}
        </View>
      )}

      {!grabando && guardadas.length > 0 && (
        <>
          <Text style={styles.seccion}>Grabaciones guardadas</Text>
          {guardadas.slice(0, 10).map((uri) => (
            <View key={uri} style={styles.fila}>
              <Text style={styles.archivo} numberOfLines={1}>
                {decodeURIComponent(uri.split('/').pop() ?? uri)}
              </Text>
              <Pressable onPress={() => compartirUri(uri)}>
                <Text style={styles.enlace}>Compartir</Text>
              </Pressable>
              <Pressable onPress={() => compartirUri(uri.replace(/\.csv$/, '_acel.csv'))}>
                <Text style={[styles.enlace, styles.enlaceSecundario]}>Acel.</Text>
              </Pressable>
            </View>
          ))}
        </>
      )}
      <Text style={styles.ayuda}>
        Mantén la app abierta mientras grabas: en iPhone, Expo Go no graba en segundo plano. Los datos se guardan
        en el teléfono cada 30 s.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  contenedor: { padding: 16, paddingBottom: 32 },
  seccion: { fontSize: 15, fontWeight: '600', marginTop: 14, marginBottom: 6 },
  opciones: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, backgroundColor: 'transparent' },
  opcion: { borderWidth: 2, borderRadius: 18, paddingVertical: 6, paddingHorizontal: 12 },
  inactivo: { opacity: 0.4 },
  textoOpcion: { fontWeight: '500' },
  textoOpcionActiva: { color: '#fff' },
  aviso: { marginTop: 8, color: '#EF6C00', fontWeight: '700' },
  ayuda: { fontSize: 12, color: COLORES.gris, marginTop: 4 },
  botonGrande: { marginTop: 18, paddingVertical: 20 },
  error: { color: COLORES.lleno, marginTop: 8 },
  tarjeta: { marginTop: 16, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: COLORES.gris, gap: 2 },
  grande: { fontSize: 32, fontWeight: '700', fontVariant: ['tabular-nums'] },
  subtitulo: { fontWeight: '600', marginTop: 8 },
  fila: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, backgroundColor: 'transparent' },
  archivo: { flex: 1, fontSize: 12, marginRight: 8 },
  enlace: { color: COLORES.miguel, fontWeight: '600' },
  enlaceSecundario: { marginLeft: 14, color: COLORES.gris },
});
