// Prueba del formato del grabador fuera del teléfono: `npm run prueba:grabador`.
// Con SALIDA_CSV=1 solo imprime una grabación sintética (5 min a pie + 5 min quieto, con el cambio
// de etiqueta en caliente), útil para probar datos/herramientas/graficar_grabacion.py.

import {
  COLUMNAS_GPS,
  encabezadoGPS,
  etiquetaAContrato,
  filaGPS,
  limpiarVelocidad,
  nombreBase,
  usuarioCasa,
  type ContextoGrabacion,
  type Etiqueta,
  type MuestraGPS,
} from '../formato';

/** Grabación sintética a 1 Hz con ruido de GPS. */
function grabacionSintetica(): MuestraGPS[] {
  let semilla = 7;
  const azar = () => ((semilla = (semilla * 16807) % 2147483647) / 2147483647) - 0.5;
  const muestras: MuestraGPS[] = [];
  const t0 = Date.UTC(2026, 9, 22, 20, 0, 0) / 1000;
  let lat = -2.9005;
  let lon = -79.0105;
  for (let i = 0; i < 600; i++) {
    const etiqueta: Etiqueta = i < 300 ? 'a_pie' : 'quieto';
    if (etiqueta === 'a_pie') {
      // ~1,3 m/s dando vueltas a una manzana de 80 m.
      const lado = Math.floor(i / 60) % 4;
      const paso = 1.3 / 111_320;
      lat += [paso, 0, -paso, 0][lado];
      lon += [0, paso, 0, -paso][lado];
    }
    const ruido = etiqueta === 'a_pie' ? 4 : 3;
    muestras.push({
      t: t0 + i + azar() * 0.05,
      lat: lat + (azar() * ruido) / 111_320,
      lon: lon + (azar() * ruido) / 111_320,
      precision_m: 4 + Math.abs(azar()) * 6,
      velocidad_mps: etiqueta === 'a_pie' ? Math.max(0, 1.3 + azar() * 0.6) : i % 7 === 0 ? null : Math.abs(azar()) * 0.3,
      etiqueta,
    });
  }
  return muestras;
}

const ctx: ContextoGrabacion = { usuario_id: usuarioCasa('Miguel', 1), persona: 'Miguel', telefono: 'android' };

if (process.env.SALIDA_CSV) {
  console.log(encabezadoGPS() + grabacionSintetica().map((m) => filaGPS(m, ctx)).join('\n'));
} else {
  let fallos = 0;
  const comprobar = (ok: boolean, desc: string) => {
    console.log(`${ok ? 'OK  ' : 'FALLA'} ${desc}`);
    if (!ok) fallos++;
  };

  comprobar(
    encabezadoGPS() === 'usuario_id,t,lat,lon,precision_m,velocidad_mps,modo_real,escenario,telefono,persona\n',
    'encabezado: 7 columnas del contrato en orden + escenario,telefono,persona',
  );
  comprobar(limpiarVelocidad(-1) === null && limpiarVelocidad(null) === null, 'speed nulo o −1 → campo vacío');
  comprobar(limpiarVelocidad(0) === 0 && limpiarVelocidad(2.5) === 2.5, 'speed válido se conserva (también 0)');
  const lento = etiquetaAContrato('vehiculo_lento');
  comprobar(lento.modo_real === 'vehiculo' && lento.escenario === 'trafico_lento', 'vehiculo_lento → vehiculo + trafico_lento');
  comprobar(etiquetaAContrato('a_pie').escenario === '', 'a_pie sin escenario');

  const fila = filaGPS(
    { t: 1761163200.25, lat: -2.8975, lon: -79.0045, precision_m: null, velocidad_mps: null, etiqueta: 'vehiculo_lento' },
    ctx,
  ).split(',');
  comprobar(fila.length === COLUMNAS_GPS.length, `fila con ${COLUMNAS_GPS.length} campos`);
  comprobar(fila[0] === 'casa_miguel_1', 'usuario_id casa_<persona>_<n>');
  comprobar(fila[4] === '' && fila[5] === '', 'precision y velocidad vacías si se desconocen');
  comprobar(fila[6] === 'vehiculo' && fila[7] === 'trafico_lento', 'modo_real y escenario en la fila');

  const nombre = nombreBase(new Date(2026, 9, 22, 9, 5, 3), 'Miguel', 'android');
  comprobar(nombre === '2026-10-22T09-05-03_miguel_android', `nombre de archivo ${nombre}`);
  comprobar(!/[:\\/ ]/.test(nombre), 'nombre válido en Windows (sin dos puntos ni espacios)');

  const sint = grabacionSintetica();
  const cambio = sint.findIndex((m) => m.etiqueta === 'quieto');
  comprobar(cambio === 300, 'grabación sintética: el cambio a quieto ocurre en la muestra 300');

  console.log(fallos === 0 ? '\nTodo OK' : `\n${fallos} comprobaciones fallaron`);
  if (fallos > 0) throw new Error('prueba del formato fallida');
}
