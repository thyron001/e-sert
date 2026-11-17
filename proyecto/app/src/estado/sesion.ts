import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useState,
  type Dispatch,
  type ReactNode,
} from 'react';

import type { Destino, EstadoSesion, Guia, SesionCerrada, SesionId } from '@/src/api/tipos';
import type { Punto } from '@/src/sesion/geo';

// Estado del flujo de parqueo que ve el usuario. Usa los estados del contrato (§3): BUSCANDO y
// GUIADO existen solo en la app (aún no hay sesion_id); desde ESTACIONADO hay sesión en el backend.
// `null` = sin flujo en curso.

export interface SesionAbierta {
  sesion_id: SesionId;
  placa: string;
  puesto_id: string;
  inicio: string; // ISO, el `ts` que la app envió al crearla
  retenido: number;
}

export interface EstadoFlujo {
  estado: EstadoSesion | null;
  partida: Punto | null;
  destino: Destino | null;
  /** Duración que el conductor dijo que quiere parquear (entrada natural, S3-3); solo informativa. */
  duracionPlanMin?: number | null;
  guia: Guia | null;
  posicion: Punto | null;
  sesion: SesionAbierta | null;
  cierre: SesionCerrada | null;
  ultimaPlaca: string;
}

export const FLUJO_INICIAL: EstadoFlujo = {
  estado: null,
  partida: null,
  destino: null,
  guia: null,
  posicion: null,
  sesion: null,
  cierre: null,
  ultimaPlaca: '',
};

export type Accion =
  | { tipo: 'RESTAURAR'; estado: EstadoFlujo }
  | { tipo: 'BUSCAR'; partida: Punto; destino: Destino; duracionPlanMin?: number | null }
  | { tipo: 'GUIA_RECIBIDA'; guia: Guia }
  | { tipo: 'AVANZAR'; posicion: Punto }
  | { tipo: 'SESION_CREADA'; sesion: SesionAbierta }
  | { tipo: 'ESTADO_SERVIDOR'; estado: EstadoSesion }
  | { tipo: 'CERRADA'; cierre: SesionCerrada }
  | { tipo: 'REINICIAR' };

/** Hay sesión en el backend que todavía no se cerró. */
export function sesionAbierta(e: EstadoFlujo): boolean {
  return e.sesion !== null && e.estado !== 'CERRADA';
}

export function reductor(e: EstadoFlujo, a: Accion): EstadoFlujo {
  switch (a.tipo) {
    case 'RESTAURAR':
      return { ...FLUJO_INICIAL, ...a.estado };
    case 'BUSCAR':
      if (sesionAbierta(e)) return e; // con una sesión abierta no se busca otro puesto
      return {
        ...FLUJO_INICIAL,
        ultimaPlaca: e.ultimaPlaca,
        estado: 'BUSCANDO',
        partida: a.partida,
        destino: a.destino,
        duracionPlanMin: a.duracionPlanMin ?? null,
      };
    case 'GUIA_RECIBIDA':
      if (e.estado !== 'BUSCANDO') return e;
      return { ...e, estado: 'GUIADO', guia: a.guia, posicion: e.partida };
    case 'AVANZAR':
      return e.estado === 'GUIADO' ? { ...e, posicion: a.posicion } : e;
    case 'SESION_CREADA':
      return { ...e, estado: 'ESTACIONADO', sesion: a.sesion, ultimaPlaca: a.sesion.placa, cierre: null };
    case 'ESTADO_SERVIDOR':
      return e.sesion ? { ...e, estado: a.estado } : e;
    case 'CERRADA':
      return e.sesion ? { ...e, estado: 'CERRADA', cierre: a.cierre } : e;
    case 'REINICIAR':
      return { ...FLUJO_INICIAL, ultimaPlaca: e.ultimaPlaca };
  }
}

export const CLAVE_FLUJO = 'esert_flujo_sesion_v1';

/** Lee el flujo guardado; si no hay o está dañado, devuelve null. */
export async function cargarFlujo(): Promise<EstadoFlujo | null> {
  try {
    const texto = await AsyncStorage.getItem(CLAVE_FLUJO);
    return texto ? ({ ...FLUJO_INICIAL, ...JSON.parse(texto) } as EstadoFlujo) : null;
  } catch {
    return null;
  }
}

export async function guardarFlujo(e: EstadoFlujo): Promise<void> {
  try {
    await AsyncStorage.setItem(CLAVE_FLUJO, JSON.stringify(e));
  } catch {
    // sin persistencia (p. ej. web sin almacenamiento): el flujo sigue en memoria
  }
}

interface ValorContexto {
  flujo: EstadoFlujo;
  despachar: Dispatch<Accion>;
  /** true cuando ya se leyó AsyncStorage (antes de eso no se debe redirigir). */
  restaurado: boolean;
}

const Contexto = createContext<ValorContexto | null>(null);

export function SesionProveedor({ children }: { children: ReactNode }) {
  const [flujo, despachar] = useReducer(reductor, FLUJO_INICIAL);
  const [restaurado, setRestaurado] = useState(false);

  useEffect(() => {
    cargarFlujo().then((guardado) => {
      if (guardado) despachar({ tipo: 'RESTAURAR', estado: guardado });
      setRestaurado(true);
    });
  }, []);

  // Se guarda en cada cambio, pero solo después de restaurar (si no, se pisaría lo guardado).
  useEffect(() => {
    if (restaurado) guardarFlujo(flujo);
  }, [flujo, restaurado]);

  const valor = useMemo(() => ({ flujo, despachar, restaurado }), [flujo, restaurado]);
  return createElement(Contexto.Provider, { value: valor }, children);
}

export function useSesion(): ValorContexto {
  const v = useContext(Contexto);
  if (!v) throw new Error('useSesion debe usarse dentro de <SesionProveedor>');
  return v;
}

/** Pantalla que corresponde al estado guardado (para recuperar el flujo al reabrir la app). */
export function rutaDelFlujo(e: EstadoFlujo): '/sesion/guiar' | '/sesion/activa' | null {
  if (e.estado === 'GUIADO' && e.guia) return '/sesion/guiar';
  if (sesionAbierta(e)) return '/sesion/activa';
  return null;
}
