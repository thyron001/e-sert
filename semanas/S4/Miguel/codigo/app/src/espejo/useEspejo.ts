import { useCallback, useEffect, useRef, useState } from 'react';

import { useAjustes } from '@/src/ajustes/AjustesContexto';
import { reportarEstadoEspejo } from '@/src/config/demo';
import { baseEspejo, urlSalud, urlWsEspejo } from '@/src/api/espejo';
import { raizApi } from '@/src/api/cliente';
import type { EstadoSesion, FinEspejo, MensajeEspejo } from '@/src/api/tipos';
import { estimarDesfase, RegistroLatencia } from './latencia';
import { NotificadorEspejo, prepararNotificaciones } from './notificaciones';
import { suscribirCierreMock } from '@/src/mocks/cierreMock';
import { SocketEspejo, type EstadoConexion } from './socketEspejo';
import { esFinEspejo, esMensajeEspejo } from './validar';

export interface Conexion {
  /** `finalizado`: llegó espejo_fin (el auto salió de la simulación); ya no se reconecta. */
  estado: EstadoConexion | 'finalizado';
  intento: number;
}

/**
 * Sigue al vehículo `vehId`: por WebSocket (CONTRATO §7) o, con el modo mock de la app
 * (EXPO_PUBLIC_USE_MOCK=1 o Ajustes), con el recorrido interno de S1-3 sin red.
 * Notifica las transiciones clave y mide la latencia evento → pantalla.
 */
export function useEspejo(vehId: string) {
  const { urlApi, modoMock } = useAjustes();
  const [mensaje, setMensaje] = useState<MensajeEspejo | null>(null);
  const [inicios, setInicios] = useState<Partial<Record<EstadoSesion, number>>>({});
  const [fin, setFin] = useState<FinEspejo | null>(null);
  // El recibo llega en un solo mensaje (contrato §7, v1.2) y el latido siguiente trae null: se
  // retiene el primer mensaje CERRADA con recibo para que no se pierda si React agrupa estados.
  const [mensajeCierre, setMensajeCierre] = useState<MensajeEspejo | null>(null);
  const [conexion, setConexion] = useState<Conexion>({ estado: 'reconectando', intento: 0 });
  const [ronda, setRonda] = useState(0);
  const [resumen, setResumen] = useState(() => new RegistroLatencia().resumen());
  const registro = useRef(new RegistroLatencia());
  const notificador = useRef(new NotificadorEspejo());
  const base = baseEspejo(urlApi);
  const modo = modoMock ? 'mock_interno' : /^https:/.test(base) ? 'vps' : 'local';

  useEffect(() => {
    prepararNotificaciones();
  }, []);

  useEffect(() => {
    setMensaje(null);
    setInicios({});
    setFin(null);
    setMensajeCierre(null);
    notificador.current.reiniciar();
    registro.current.vaciar();
    let vivo = true;

    const alMensaje = (m: MensajeEspejo, recibidoEn: number) => {
      setMensaje(m);
      if (m.estado === 'CERRADA' && m.recibo) setMensajeCierre((previo) => previo ?? m);
      if (m.estado) {
        const estado = m.estado;
        setInicios((prev) => (estado in prev ? prev : { ...prev, [estado]: m.t_sim }));
      }
      notificador.current.procesar(m);
      // El pintado ocurre en el cuadro siguiente al setState.
      requestAnimationFrame(() => {
        if (!vivo) return;
        registro.current.registrar({ t_sim: m.t_sim, ts: m.ts, recibidoEn, pintadoEn: Date.now() });
        if (registro.current.muestras.length % 5 === 0) setResumen(registro.current.resumen());
      });
    };
    const alFin = (m: FinEspejo) => {
      setFin(m);
      setConexion({ estado: 'finalizado', intento: 0 });
      setResumen(registro.current.resumen());
      if (!modoMock) enviarLatencias(base, registro.current.aCSV(modo));
    };

    if (modoMock) {
      setConexion({ estado: 'en_vivo', intento: 0 });
      // MOCK: recorrido de S1-3/S2-3 con CERRADA y recibo 20 s después de ESTACIONADO (S3-1).
      const quitar = suscribirCierreMock(vehId, (m) => {
        if (esFinEspejo(m)) return alFin(m);
        if (esMensajeEspejo(m)) alMensaje(m, Date.now());
      });
      return () => {
        vivo = false;
        quitar();
      };
    }

    // Primero el desfase (hasta 5 peticiones a /salud) y luego el socket, para que ninguna
    // muestra de latencia use desfase 0. Si /salud falla, se conecta igual.
    const socket = new SocketEspejo((id) => urlWsEspejo(base, id));
    estimarDesfase(urlSalud(base))
      .then((d) => {
        registro.current.desfaseMs = d.desfaseMs;
      })
      .catch(() => {
        // sin estimación: lat_total supone relojes sincronizados; lat_cliente no se afecta
      })
      .finally(() => {
        if (!vivo) return;
        socket.conectar(vehId, {
          onMensaje: alMensaje,
          onFin: alFin,
          onEstado: (estado, intento) => setConexion({ estado, intento }),
        });
      });
    return () => {
      vivo = false;
      socket.cerrar();
    };
  }, [vehId, base, modoMock, modo, ronda]);

  // Ajustes de demo muestra el estado del WebSocket del espejo abierto.
  useEffect(() => {
    reportarEstadoEspejo(modoMock ? 'mock' : conexion.estado, vehId);
    return () => reportarEstadoEspejo('cerrado', null);
  }, [conexion.estado, vehId, modoMock]);

  const reiniciar = useCallback(() => setRonda((r) => r + 1), []);

  return { mensaje, mensajeCierre, inicios, fin, conexion, modo, resumen, registro: registro.current, reiniciar };
}

// MOCK: solo el servidor de app/mock_espejo/ acepta este POST; sirve para juntar las latencias
// del teléfono en la computadora sin pasar el CSV a mano. Si no existe, se ignora.
function enviarLatencias(base: string, csv: string): void {
  fetch(`${raizApi(base)}/espejo/latencias`, { method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: csv }).catch(
    () => undefined,
  );
}
