import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, ScrollView, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { cerrarSesion, getBilletera, mensajeUsuario } from '@/src/api/cliente';
import { TARIFA } from '@/src/api/tarifa';
import { BannerAvisos } from '@/src/espejo/componentes/BannerAvisos';
import { useSesion } from '@/src/estado/sesion';
import { avisosVencidos, cancelarAvisos, dispararSiVencio, leerProgramados, type Programados } from '@/src/servicios/avisos';
import { DetectorCierre, usarSeguimientoPropio, type DatosRecibo } from '@/src/servicios/seguimientoSesion';
import { cronometro, resumenCobro } from '@/src/sesion/cobro';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

const REFRESCO_SALDO_MS = 15_000;

// Sesión activa: el costo se calcula en el teléfono con tarifa.json; el cobro real lo hace el
// backend al cerrar. El cierre puede venir de "Ya me voy" o de fuera de la app (la simulación o
// un `curl .../cerrar`), que se detecta con GET /sesiones/{id} cada 10 s. En ambos casos se pasa
// al recibo con router.replace, una sola vez.
export default function Activa() {
  const { api, usuarioId } = useAjustes();
  const { flujo, despachar } = useSesion();
  const { sesion, cierre } = flujo;
  const [ahora, setAhora] = useState(() => Date.now());
  const [saldo, setSaldo] = useState<number | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [huerfana, setHuerfana] = useState(false);
  const [programados, setProgramados] = useState<Programados | null>(null);
  const detector = useRef(
    new DetectorCierre({ origen: 'propia', usuario_id: usuarioId, placa: sesion?.placa ?? null }),
  ).current;
  const navegado = useRef(false); // candado: el recibo se abre una sola vez

  const irAlRecibo = useCallback(
    (d: DatosRecibo) => {
      if (navegado.current) return;
      navegado.current = true;
      cancelarAvisos(); // al cerrar no queda ninguna notificación pendiente
      despachar({
        tipo: 'CERRADA',
        cierre: {
          sesion_id: d.sesion_id ?? sesion?.sesion_id ?? '',
          minutos_reales: d.minutos_reales,
          minutos_cobrados: d.minutos_cobrados,
          debitado: d.cobrado_usd,
          saldo: d.saldo ?? 0,
        },
      });
      router.replace({ pathname: '/recibo', params: { datos: JSON.stringify(d) } });
    },
    [despachar, sesion?.sesion_id],
  );

  // Cronómetro a 1 Hz mientras la pantalla tiene el foco.
  useFocusEffect(
    useCallback(() => {
      const id = setInterval(() => setAhora(Date.now()), 1000);
      return () => clearInterval(id);
    }, []),
  );

  // Avisos programados al llegar (o reprogramados tras una recarga): se releen al tomar el foco.
  // confirmar los programa en segundo plano después de abrir esta pantalla: se releen cada 2 s.
  useFocusEffect(
    useCallback(() => {
      const leer = () => leerProgramados().then(setProgramados);
      leer();
      const id = setInterval(leer, 2000);
      return () => clearInterval(id);
    }, []),
  );

  // Saldo para los avisos (cada 15 s).
  useFocusEffect(
    useCallback(() => {
      const leer = () =>
        getBilletera(usuarioId, api)
          .then((b) => setSaldo(b.saldo))
          .catch(() => undefined);
      leer();
      const id = setInterval(leer, REFRESCO_SALDO_MS);
      return () => clearInterval(id);
    }, [api, usuarioId]),
  );

  useEffect(() => {
    if (sesion) detector.conocerSesion(sesion.sesion_id, { puesto_id: sesion.puesto_id, inicio: sesion.inicio });
  }, [detector, sesion]);

  // Cierre hecho fuera de la app: GET /sesiones/{id} cada 10 s y al volver a primer plano.
  // Mientras se envía "Ya me voy" se pausa el sondeo, para que el cierre conserve su motivo (manual).
  usarSeguimientoPropio(detector, sesion && !cierre && !ocupado ? sesion.sesion_id : null, api, irAlRecibo, () =>
    setHuerfana(true),
  );

  useEffect(() => {
    if (!sesion) router.replace('/sesion');
  }, [sesion]);

  // Si la app se reabre con una sesión ya cerrada (estado persistido), se muestra su recibo.
  useEffect(() => {
    if (sesion && cierre && !navegado.current) {
      navegado.current = true;
      const d: DatosRecibo = {
        origen: 'propia',
        motivo: null,
        sesion_id: cierre.sesion_id,
        veh_id: null,
        usuario_id: usuarioId,
        placa: sesion.placa,
        puesto_id: sesion.puesto_id,
        inicio: sesion.inicio,
        fin: null,
        minutos_reales: cierre.minutos_reales,
        minutos_cobrados: cierre.minutos_cobrados,
        cobrado_usd: cierre.debitado,
        tarjeta_sert_usd: null,
        ahorro_usd: null,
        saldo: cierre.saldo,
      };
      router.replace({ pathname: '/recibo', params: { datos: JSON.stringify(d) } });
    }
  }, [sesion, cierre, usuarioId]);

  // App abierta: el aviso vencido se notifica ya (no a la hora inexacta de Android).
  const tiposVencidos =
    sesion && programados?.sesion_id === sesion.sesion_id
      ? avisosVencidos(programados, ahora)
          .map((v) => v.tipo)
          .join(',')
      : '';
  useEffect(() => {
    tiposVencidos
      .split(',')
      .filter(Boolean)
      .forEach((tipo) => dispararSiVencio(tipo as Programados['avisos'][number]['tipo']));
  }, [tiposVencidos]);

  if (!sesion || cierre) return null;

  const segundos = (ahora - new Date(sesion.inicio).getTime()) / 1000;
  const r = resumenCobro(segundos / 60, saldo);
  // Banner propio con los avisos programados ya vencidos (en iPhone la app hace poco en segundo
  // plano). Los de "cerca" del cálculo en vivo se omiten para no repetirlos.
  const vencidos = programados?.sesion_id === sesion.sesion_id ? avisosVencidos(programados, ahora) : [];
  const enVivo = vencidos.length ? r.avisos.filter((x) => x === 'saldo_agotado' || x === 'tiempo_maximo_superado') : r.avisos;

  async function cerrarManual() {
    if (!sesion) return;
    setOcupado(true);
    setError(null);
    try {
      const c = await cerrarSesion(sesion.sesion_id, { ts: new Date().toISOString(), motivo: 'manual' }, api);
      const ev = detector.cierreManual(c, { puesto_id: sesion.puesto_id, inicio: sesion.inicio });
      if (ev?.tipo === 'cierre') irAlRecibo(ev.datos);
    } catch (e) {
      setError(mensajeUsuario(e));
    } finally {
      setOcupado(false);
    }
  }

  function yaMeVoy() {
    Alert.alert('¿Terminar la sesión?', `Se cobrará el tiempo usado (${r.minutosCobrables} min, ${usd(r.costo)}).`, [
      { text: 'Seguir estacionado', style: 'cancel' },
      { text: 'Sí, ya me voy', style: 'destructive', onPress: cerrarManual },
    ]);
  }

  return (
    <ScrollView contentContainerStyle={estilos.contenedor} contentInsetAdjustmentBehavior="automatic">
      <Text style={estilos.titulo}>Sesión activa</Text>
      <Text style={estilos.detalle}>
        {sesion.placa} · {sesion.puesto_id}
      </Text>
      <Text style={estilos.reloj}>{cronometro(segundos)}</Text>
      {vencidos.map((v) => (
        <View key={v.tipo} style={estilos.aviso}>
          <Text style={estilos.avisoTitulo}>⚠️ {v.titulo}</Text>
          <Text style={estilos.avisoTexto}>{v.cuerpo}</Text>
        </View>
      ))}
      <BannerAvisos avisos={enVivo} />
      <View style={estilos.tarjeta}>
        <Fila etiqueta="Minutos cobrables" valor={`${r.minutosCobrables} min`} />
        <Fila etiqueta="Costo acumulado" valor={usd(r.costo)} fuerte />
        <Fila etiqueta="Retenido" valor={usd(sesion.retenido)} />
        {saldo !== null && <Fila etiqueta="Saldo" valor={usd(saldo)} />}
        <Fila
          etiqueta="Tope SERT"
          valor={r.restanteMin >= 0 ? `faltan ${Math.ceil(r.restanteMin)} min de ${TARIFA.tiempo_maximo_min}` : 'superado'}
        />
      </View>
      <Text style={estilos.nota}>
        Fracciones de {TARIFA.fraccion_min} min, mínimo {TARIFA.cobro_minimo_min} min, a {usd(TARIFA.valor_hora_usd)}/h. Si
        la simulación detecta que te fuiste, el recibo se abre solo.
      </Text>
      {error && <Text style={estilos.error}>{error}</Text>}
      {huerfana ? (
        <>
          <Text style={estilos.error}>
            El servidor ya no tiene esta sesión (se guardó con otro backend o se borró). No se puede cerrar ni cobrar.
          </Text>
          <Boton
            texto="Descartar sesión"
            onPress={() => {
              cancelarAvisos();
              despachar({ tipo: 'REINICIAR' });
              router.replace('/sesion');
            }}
          />
        </>
      ) : (
        <Boton texto="Ya me voy" onPress={yaMeVoy} ocupado={ocupado} />
      )}
    </ScrollView>
  );
}

function Fila({ etiqueta, valor, fuerte = false }: { etiqueta: string; valor: string; fuerte?: boolean }) {
  return (
    <View style={estilos.fila}>
      <Text style={estilos.filaEtiqueta}>{etiqueta}</Text>
      <Text style={[estilos.filaValor, fuerte && estilos.fuerte]}>{valor}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  contenedor: { padding: 16 },
  titulo: { fontSize: 24, fontWeight: '800', color: COLORES.miguel },
  detalle: { color: COLORES.gris, marginBottom: 4 },
  reloj: { fontSize: 56, fontWeight: '800', fontVariant: ['tabular-nums'], textAlign: 'center', marginVertical: 12 },
  tarjeta: {
    padding: 12,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: COLORES.gris,
    marginBottom: 8,
  },
  fila: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, backgroundColor: 'transparent' },
  filaEtiqueta: { color: COLORES.gris },
  filaValor: { fontWeight: '600', fontVariant: ['tabular-nums'] },
  fuerte: { fontSize: 20, fontWeight: '800', color: COLORES.miguel },
  nota: { color: COLORES.gris, fontSize: 12, marginBottom: 4 },
  error: { color: COLORES.lleno, marginTop: 6 },
  aviso: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#F9A825',
    backgroundColor: '#FFF8E1',
    marginBottom: 8,
  },
  avisoTitulo: { fontWeight: '800', color: '#6D4C00' },
  avisoTexto: { color: '#6D4C00', marginTop: 2 },
});
