import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { MOCK_POR_DEFECTO, URL_POR_DEFECTO, crearClienteHttp } from '@/src/api/cliente';
import { crearClienteMock } from '@/src/api/mock';
import { guardarUrlDemo, leerUrlDemo } from '@/src/config/demo';
import type { ApiESert, UsuarioId } from '@/src/api/tipos';

const CLAVE_URL = 'esert_api_url';
const CLAVE_MOCK = 'esert_modo_mock';
const CLAVE_USUARIO = 'esert_usuario_id';

// SecureStore no existe en web: ahí los ajustes viven solo en memoria.
async function leer(clave: string): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(clave);
  } catch {
    return null;
  }
}

async function guardar(clave: string, valor: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(clave, valor);
  } catch {
    // sin persistencia
  }
}

interface Ajustes {
  cargado: boolean;
  urlApi: string;
  modoMock: boolean;
  usuarioId: UsuarioId;
  api: ApiESert;
  cambiarUrl(url: string): Promise<void>;
  cambiarModoMock(activo: boolean): Promise<void>;
}

const Contexto = createContext<Ajustes | null>(null);

// Un único mock por ejecución de la app, para que la billetera en memoria no se pierda al
// cambiar de pantalla o al apagar y volver a encender el modo mock.
const mockCompartido = crearClienteMock();

export function AjustesProveedor({ children }: { children: ReactNode }) {
  const [cargado, setCargado] = useState(false);
  const [urlApi, setUrlApi] = useState(URL_POR_DEFECTO);
  // EXPO_PUBLIC_USE_MOCK decide el valor inicial; luego manda lo guardado en Ajustes.
  const [modoMock, setModoMock] = useState(MOCK_POR_DEFECTO);
  const [usuarioId, setUsuarioId] = useState<UsuarioId>('');

  useEffect(() => {
    (async () => {
      const [urlDemo, url, mock, usuario] = await Promise.all([
        leerUrlDemo(),
        leer(CLAVE_URL),
        leer(CLAVE_MOCK),
        leer(CLAVE_USUARIO),
      ]);
      // La URL de "Ajustes de demo" (AsyncStorage) manda sobre la de Ajustes y sobre .env.
      if (urlDemo) setUrlApi(urlDemo);
      else if (url) setUrlApi(url);
      if (mock !== null) setModoMock(mock === '1');
      let id = usuario;
      if (!id) {
        id = `app_${Crypto.randomUUID()}`;
        await guardar(CLAVE_USUARIO, id);
      }
      setUsuarioId(id);
      setCargado(true);
    })();
  }, []);

  const cambiarUrl = useCallback(async (url: string) => {
    const limpia = url.trim().replace(/\/+$/, '');
    setUrlApi(limpia);
    await Promise.all([guardar(CLAVE_URL, limpia), guardarUrlDemo(limpia)]);
  }, []);

  const cambiarModoMock = useCallback(async (activo: boolean) => {
    setModoMock(activo);
    await guardar(CLAVE_MOCK, activo ? '1' : '0');
  }, []);

  const api = useMemo(() => (modoMock ? mockCompartido : crearClienteHttp(urlApi)), [modoMock, urlApi]);

  const valor = useMemo(
    () => ({ cargado, urlApi, modoMock, usuarioId, api, cambiarUrl, cambiarModoMock }),
    [cargado, urlApi, modoMock, usuarioId, api, cambiarUrl, cambiarModoMock],
  );

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useAjustes(): Ajustes {
  const ajustes = useContext(Contexto);
  if (!ajustes) throw new Error('useAjustes debe usarse dentro de <AjustesProveedor>');
  return ajustes;
}
