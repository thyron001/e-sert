import { useFonts } from 'expo-font';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider, router } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect, useRef } from 'react';
import 'react-native-reanimated';

import { useColorScheme } from '@/components/useColorScheme';
import { AjustesProveedor } from '@/src/ajustes/AjustesContexto';
import { SesionProveedor, rutaDelFlujo, useSesion } from '@/src/estado/sesion';

export {
  // Catch any errors thrown by the Layout component.
  ErrorBoundary,
} from 'expo-router';

// Prevent the splash screen from auto-hiding before asset loading is complete.
SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [loaded, error] = useFonts({
    SpaceMono: require('../assets/fonts/SpaceMono-Regular.ttf'),
  });

  // Expo Router uses Error Boundaries to catch errors in the navigation tree.
  useEffect(() => {
    if (error) throw error;
  }, [error]);

  useEffect(() => {
    if (loaded) {
      SplashScreen.hideAsync();
    }
  }, [loaded]);

  if (!loaded) {
    return null;
  }

  return <RootLayoutNav />;
}

function RootLayoutNav() {
  const colorScheme = useColorScheme();

  return (
    <AjustesProveedor>
      <SesionProveedor>
        <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
          <RecuperarFlujo />
          <Stack>
            <Stack.Screen name="(tabs)" options={{ headerShown: false, title: 'Inicio' }} />
            <Stack.Screen name="buscar" options={{ title: 'Buscar puesto' }} />
            <Stack.Screen name="recarga" options={{ title: 'Recarga', presentation: 'modal' }} />
            <Stack.Screen name="sesion/guiar" options={{ title: 'Guiado', gestureEnabled: false }} />
            <Stack.Screen name="sesion/confirmar" options={{ title: 'Confirmar llegada' }} />
            <Stack.Screen name="sesion/activa" options={{ title: 'Sesión', gestureEnabled: false }} />
            <Stack.Screen name="espejo/index" options={{ title: 'Modo espejo' }} />
            <Stack.Screen name="espejo/[vehId]" options={{ title: 'Espejo' }} />
          </Stack>
        </ThemeProvider>
      </SesionProveedor>
    </AjustesProveedor>
  );
}

// Al reabrir la app con un guiado o una sesión abierta guardados, vuelve a esa pantalla (una vez).
function RecuperarFlujo() {
  const { flujo, restaurado } = useSesion();
  const hecho = useRef(false);
  useEffect(() => {
    if (!restaurado || hecho.current) return;
    hecho.current = true;
    const ruta = rutaDelFlujo(flujo);
    if (ruta) router.push(ruta);
  }, [restaurado, flujo]);
  return null;
}
