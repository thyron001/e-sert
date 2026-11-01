// Geometría simple para el guiado simulado (el teléfono no se mueve: la posición avanza sola).
export interface Punto {
  lat: number;
  lon: number;
}

const RADIO_TIERRA_M = 6_371_000;
const rad = (g: number) => (g * Math.PI) / 180;

/** Distancia haversine en metros. */
export function haversineM(a: Punto, b: Punto): number {
  const dLat = rad(b.lat - a.lat);
  const dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * RADIO_TIERRA_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Avanza `pasoM` metros en línea recta de `desde` hacia `hasta`, sin pasarse. */
export function simularAvance(desde: Punto, hasta: Punto, pasoM: number): Punto {
  const d = haversineM(desde, hasta);
  if (d <= pasoM || d === 0) return { ...hasta };
  const f = pasoM / d;
  return { lat: desde.lat + (hasta.lat - desde.lat) * f, lon: desde.lon + (hasta.lon - desde.lon) * f };
}

/** Velocidad simulada del auto en el Centro (~29 km/h) y radio en el que se considera llegado. */
export const VELOCIDAD_SIM_MPS = 8;
export const RADIO_LLEGADA_M = 25;

/** Partida por defecto: esquina de la Gran Colombia y Benigno Malo (cruce de las dos calles en puestos.csv). */
export const PARTIDA_POR_DEFECTO: Punto = { lat: -2.895833, lon: -79.004625 };
