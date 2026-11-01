import { router } from 'expo-router';
import { useEffect } from 'react';

// Deep link de vuelta de Payphone (esert://pagos/retorno). En iOS lo atrapa
// openAuthSessionAsync; en Android también puede llegar al router: se vuelve a la pantalla
// de Recarga, que es la que consulta el estado del pago.
export default function RetornoPago() {
  useEffect(() => {
    if (router.canGoBack()) router.back();
    else router.replace('/recarga');
  }, []);
  return null;
}
