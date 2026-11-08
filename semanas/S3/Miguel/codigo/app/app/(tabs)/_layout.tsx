import { SymbolView, type SymbolViewProps } from 'expo-symbols';
import { Tabs } from 'expo-router';
import type { ColorValue } from 'react-native';

import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useClientOnlyValue } from '@/components/useClientOnlyValue';

function icono(nombre: SymbolViewProps['name']) {
  return ({ color }: { color: ColorValue }) => <SymbolView name={nombre} tintColor={color} size={26} />;
}

export default function TabLayout() {
  const colorScheme = useColorScheme();

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: Colors[colorScheme].tint,
        // Disable the static render of the header on web
        // to prevent a hydration error in React Navigation v6.
        headerShown: useClientOnlyValue(false, true),
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Mapa',
          tabBarIcon: icono({ ios: 'map', android: 'map', web: 'map' }),
        }}
      />
      <Tabs.Screen
        name="sesion"
        options={{
          title: 'Sesión',
          tabBarIcon: icono({ ios: 'car.fill', android: 'directions_car', web: 'directions_car' }),
        }}
      />
      <Tabs.Screen
        name="billetera"
        options={{
          title: 'Billetera',
          tabBarIcon: icono({
            ios: 'creditcard',
            android: 'account_balance_wallet',
            web: 'account_balance_wallet',
          }),
        }}
      />
      <Tabs.Screen
        name="grabador"
        options={{
          title: 'Grabador',
          tabBarIcon: icono({
            ios: 'record.circle',
            android: 'fiber_manual_record',
            web: 'fiber_manual_record',
          }),
        }}
      />
      <Tabs.Screen
        name="ajustes"
        options={{
          title: 'Ajustes',
          tabBarIcon: icono({ ios: 'gearshape', android: 'settings', web: 'settings' }),
        }}
      />
    </Tabs>
  );
}
