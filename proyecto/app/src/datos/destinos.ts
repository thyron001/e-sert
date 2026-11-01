// Copia de proyecto/sumo/demanda/destinos.csv (Tyrone, S1), generada con scripts/destinos.py.
// No editar a mano: si cambia el CSV, vuelve a ejecutar el script.
import type { Destino } from '@/src/api/tipos';

export interface DestinoApp extends Destino {
  peso: number;
}

export const DESTINOS: DestinoApp[] = [
  { nombre: "Parque Calderón", lat: -2.897308, lon: -79.004488, peso: 3 },
  { nombre: "Catedral Nueva", lat: -2.897443, lon: -79.005237, peso: 1 },
  { nombre: "Mercado 10 de Agosto", lat: -2.899212, lon: -79.007545, peso: 2 },
  { nombre: "Mercado 9 de Octubre", lat: -2.895351, lon: -79.00127, peso: 2 },
  { nombre: "Plaza San Francisco", lat: -2.898654, lon: -79.006578, peso: 1 },
  { nombre: "Municipio (Bolívar y Borrero)", lat: -2.897387, lon: -79.003117, peso: 1 },
  { nombre: "Plaza de las Flores", lat: -2.897699, lon: -79.005837, peso: 1 },
  { nombre: "Museo Pumapungo", lat: -2.906139, lon: -78.996844, peso: 1 },
  { nombre: "Plaza del Otorongo", lat: -2.89802, lon: -79.011116, peso: 1 },
  { nombre: "Santo Domingo", lat: -2.895256, lon: -79.006198, peso: 1 },
  { nombre: "San Sebastián", lat: -2.895716, lon: -79.011163, peso: 1 },
  { nombre: "Banco en la Gran Colombia", lat: -2.896288, lon: -79.0031, peso: 1 },
];
