import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useMemo, useState } from 'react';
import { Alert, ScrollView, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { getBilletera } from '@/src/api/cliente';
import type { MotivoCierre } from '@/src/api/tipos';
import { bloquesTarjetaSert, compararConServidor, costo, costoTarjetaSert, TARIFA } from '@/src/logica/tarifa';
import type { DatosRecibo } from '@/src/servicios/seguimientoSesion';
import { COLORES } from '@/src/ui/colores';
import { Boton, usd } from '@/src/ui/comunes';

export const CLAVE_RECLAMOS = 'esert_reclamos_cierre_v1';

const TEXTO_MOTIVO: Record<MotivoCierre, string> = {
  deteccion: 'La simulación detectó que te fuiste',
  manual: 'Cerraste la sesión',
  timeout_sin_senal: 'Cierre por falta de señal',
};

/** Hora en America/Guayaquil (UTC−5, sin horario de verano), sin depender de Intl en Hermes. */
export function horaGuayaquil(iso: string | null): string {
  if (!iso) return '—';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return '—';
  const d = new Date(t - 5 * 3600_000);
  const dos = (n: number) => String(n).padStart(2, '0');
  return `${dos(d.getUTCDate())}/${dos(d.getUTCMonth() + 1)} ${dos(d.getUTCHours())}:${dos(d.getUTCMinutes())}`;
}

/** Tarjeta SERT y ahorro: los del servidor si vienen (espejo); si no, calculados con tarifa.ts. */
export function comparacionTarjeta(d: DatosRecibo) {
  const tarjeta = d.tarjeta_sert_usd ?? costoTarjetaSert(d.minutos_reales);
  const ahorro = d.ahorro_usd ?? Math.round((tarjeta - d.cobrado_usd) * 100) / 100;
  return { tarjeta, ahorro, bloques: bloquesTarjetaSert(d.minutos_reales), delServidor: d.tarjeta_sert_usd !== null };
}

/** Comprobación local: los montos mostrados son los del servidor; si tarifa.ts difiere > $0,01, avisa. */
function comprobar(d: DatosRecibo): void {
  if (d.tarjeta_sert_usd !== null && d.ahorro_usd !== null) {
    const r = compararConServidor({
      minutos_reales: d.minutos_reales,
      minutos_cobrados: d.minutos_cobrados,
      cobrado_usd: d.cobrado_usd,
      tarjeta_sert_usd: d.tarjeta_sert_usd,
      ahorro_usd: d.ahorro_usd,
    });
    if (!r.ok) console.warn('[recibo] el recibo del servidor no cuadra con tarifa.ts:', r.diferencias);
  } else if (Math.abs(costo(d.minutos_reales) - d.cobrado_usd) > 0.01) {
    console.warn(`[recibo] cobrado ${d.cobrado_usd} ≠ tarifa.ts ${costo(d.minutos_reales)}`);
  }
}

export function Recibo({ datos, alTerminar }: { datos: DatosRecibo; alTerminar: () => void }) {
  const { api } = useAjustes();
  const [saldo, setSaldo] = useState<number | null>(datos.saldo);
  const [calle, setCalle] = useState<string | null>(null);
  const [reclamado, setReclamado] = useState(false);
  const { tarjeta, ahorro, bloques, delServidor } = useMemo(() => comparacionTarjeta(datos), [datos]);

  useEffect(() => comprobar(datos), [datos]);

  // Saldo restante (GET /billetera) y calle del puesto (GET /puestos), si el servidor los tiene.
  useEffect(() => {
    if (datos.usuario_id) {
      getBilletera(datos.usuario_id, api)
        .then((b) => setSaldo(b.saldo))
        .catch(() => undefined);
    }
    if (datos.puesto_id) {
      api
        .listarPuestos()
        .then((ps) => setCalle(ps.find((p) => p.puesto_id === datos.puesto_id)?.calle ?? null))
        .catch(() => undefined);
    }
  }, [api, datos.usuario_id, datos.puesto_id]);

  async function avisar() {
    try {
      const previos = JSON.parse((await AsyncStorage.getItem(CLAVE_RECLAMOS)) ?? '[]') as unknown[];
      previos.push({ reportado: new Date().toISOString(), datos });
      await AsyncStorage.setItem(CLAVE_RECLAMOS, JSON.stringify(previos));
      setReclamado(true);
    } catch (e) {
      console.warn('[recibo] no se pudo guardar el aviso', e);
      Alert.alert('No se pudo guardar', 'Inténtalo de nuevo.');
    }
  }

  const motivo = datos.motivo ? TEXTO_MOTIVO[datos.motivo] : 'El servidor registró el cierre de la sesión';

  return (
    <ScrollView contentContainerStyle={estilos.contenedor} contentInsetAdjustmentBehavior="automatic">
      <Text style={estilos.titulo}>Recibo</Text>
      <Text style={estilos.motivo}>{motivo}</Text>

      <View style={estilos.tarjeta}>
        <Fila etiqueta={datos.placa ? 'Placa' : 'Vehículo'} valor={datos.placa ?? datos.veh_id ?? '—'} />
        <Fila etiqueta="Puesto" valor={datos.puesto_id ?? '—'} />
        {calle && <Fila etiqueta="Calle" valor={calle} />}
        <Fila etiqueta="Llegada" valor={horaGuayaquil(datos.inicio)} />
        <Fila etiqueta="Salida" valor={horaGuayaquil(datos.fin)} />
      </View>

      <View style={estilos.tarjeta}>
        <Fila etiqueta="Tiempo real" valor={`${datos.minutos_reales.toFixed(1).replace(".", ",")} min`} />
        <Fila etiqueta="Tiempo cobrado" valor={`${datos.minutos_cobrados} min (fracciones de ${TARIFA.fraccion_min})`} />
        <Fila etiqueta="Débito" valor={usd(datos.cobrado_usd)} fuerte />
        <Fila etiqueta="Saldo restante" valor={saldo !== null ? usd(saldo) : '—'} />
      </View>

      <View style={[estilos.tarjeta, estilos.comparacion]}>
        <Text style={estilos.tarjetaTexto}>
          Con la tarjeta SERT habrías pagado {usd(tarjeta)} ({bloques} {bloques === 1 ? 'bloque' : 'bloques'} de{' '}
          {TARIFA.tarjeta_bloque_min} min).
        </Text>
        <Text style={estilos.ahorro}>
          {ahorro > 0 ? `Ahorraste ${usd(ahorro)}` : 'Pagaste lo mismo que con la tarjeta'}
        </Text>
        {!delServidor && <Text style={estilos.nota}>Tarjeta calculada con la tarifa vigente.</Text>}
      </View>

      <Boton texto="Listo" onPress={alTerminar} />
      {reclamado ? (
        <Text style={estilos.nota}>Gracias: guardamos el caso para revisarlo.</Text>
      ) : (
        <Boton texto="¿No te fuiste? Avísanos" onPress={avisar} style={estilos.secundario} />
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
  titulo: { fontSize: 28, fontWeight: '800', color: COLORES.miguel },
  motivo: { color: COLORES.gris, marginBottom: 12 },
  tarjeta: {
    padding: 12,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: COLORES.gris,
    marginBottom: 10,
  },
  comparacion: { borderColor: COLORES.libre, borderWidth: 1 },
  tarjetaTexto: { fontSize: 15 },
  ahorro: { fontSize: 20, fontWeight: '800', color: COLORES.libre, marginTop: 6 },
  fila: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, backgroundColor: 'transparent' },
  filaEtiqueta: { color: COLORES.gris },
  filaValor: { fontWeight: '600', fontVariant: ['tabular-nums'], flexShrink: 1, textAlign: 'right' },
  fuerte: { fontSize: 20, fontWeight: '800', color: COLORES.miguel },
  nota: { color: COLORES.gris, fontSize: 12, marginTop: 6, textAlign: 'center' },
  secundario: { backgroundColor: COLORES.gris },
});
