import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ScrollView, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { cerrarSesion, getBilletera, getSesion, mensajeUsuario } from '@/src/api/cliente';
import { TARIFA } from '@/src/api/tarifa';
import { BannerAvisos } from '@/src/espejo/componentes/BannerAvisos';
import { useSesion } from '@/src/estado/sesion';
import { cronometro, resumenCobro } from '@/src/sesion/cobro';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

const REFRESCO_SERVIDOR_MS = 15_000;

// Sesión activa: el costo se calcula en el teléfono con tarifa.json; el cobro real lo hace el
// backend al cerrar. El cierre automático por detección es de S3: aquí solo "Terminar" (manual).
export default function Activa() {
  const { api, usuarioId } = useAjustes();
  const { flujo, despachar } = useSesion();
  const { sesion, cierre } = flujo;
  const [ahora, setAhora] = useState(() => Date.now());
  const [saldo, setSaldo] = useState<number | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Cronómetro a 1 Hz mientras la pantalla tiene el foco.
  useFocusEffect(
    useCallback(() => {
      const id = setInterval(() => setAhora(Date.now()), 1000);
      return () => clearInterval(id);
    }, []),
  );

  // Saldo y estado desde el backend al entrar y cada 15 s (por si la sesión se cerró en otro lado).
  const sincronizar = useCallback(async () => {
    if (!sesion || cierre) return;
    try {
      const [b, s] = await Promise.all([getBilletera(usuarioId, api), getSesion(sesion.sesion_id, api)]);
      setSaldo(b.saldo);
      if (s.estado === 'CERRADA') {
        despachar({
          tipo: 'CERRADA',
          cierre: {
            sesion_id: s.sesion_id,
            minutos_reales: s.minutos_reales ?? 0,
            minutos_cobrados: s.minutos_cobrados ?? 0,
            debitado: s.debitado ?? 0,
            saldo: b.saldo,
          },
        });
      } else if (s.estado !== flujo.estado) {
        despachar({ tipo: 'ESTADO_SERVIDOR', estado: s.estado });
      }
    } catch {
      // sin red: se sigue mostrando el cálculo local
    }
  }, [api, usuarioId, sesion, cierre, flujo.estado, despachar]);

  useFocusEffect(
    useCallback(() => {
      sincronizar();
      const id = setInterval(sincronizar, REFRESCO_SERVIDOR_MS);
      return () => clearInterval(id);
    }, [sincronizar]),
  );

  useEffect(() => {
    if (!sesion) router.replace('/sesion');
  }, [sesion]);

  if (!sesion) return null;

  const segundos = (ahora - new Date(sesion.inicio).getTime()) / 1000;
  const r = resumenCobro(segundos / 60, saldo);

  async function terminar() {
    if (!sesion) return;
    setOcupado(true);
    setError(null);
    try {
      const c = await cerrarSesion(sesion.sesion_id, { ts: new Date().toISOString(), motivo: 'manual' }, api);
      despachar({ tipo: 'CERRADA', cierre: c });
    } catch (e) {
      setError(mensajeUsuario(e));
    } finally {
      setOcupado(false);
    }
  }

  if (cierre) {
    return (
      <ScrollView contentContainerStyle={estilos.contenedor} contentInsetAdjustmentBehavior="automatic">
        <Text style={estilos.titulo}>Sesión cerrada</Text>
        <View style={estilos.tarjeta}>
          <Fila etiqueta="Tiempo real" valor={`${cierre.minutos_reales.toFixed(1)} min`} />
          <Fila etiqueta="Tiempo cobrado" valor={`${cierre.minutos_cobrados} min`} />
          <Fila etiqueta="Cobrado" valor={usd(cierre.debitado)} fuerte />
          <Fila etiqueta="Retención liberada" valor={usd(sesion.retenido)} />
          <Fila etiqueta="Saldo" valor={usd(cierre.saldo)} />
        </View>
        <Boton
          texto="Volver al inicio"
          onPress={() => {
            despachar({ tipo: 'REINICIAR' });
            router.replace('/sesion');
          }}
        />
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={estilos.contenedor} contentInsetAdjustmentBehavior="automatic">
      <Text style={estilos.titulo}>Sesión activa</Text>
      <Text style={estilos.detalle}>
        {sesion.placa} · {sesion.puesto_id}
      </Text>
      <Text style={estilos.reloj}>{cronometro(segundos)}</Text>
      <BannerAvisos avisos={r.avisos} />
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
        Fracciones de {TARIFA.fraccion_min} min, mínimo {TARIFA.cobro_minimo_min} min, a {usd(TARIFA.valor_hora_usd)}/h.
      </Text>
      {error && <Text style={estilos.error}>{error}</Text>}
      <Boton texto="Terminar" onPress={terminar} ocupado={ocupado} />
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
});
