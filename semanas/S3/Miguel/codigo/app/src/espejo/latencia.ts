// Latencia evento → pantalla del modo espejo.
//
// lat_total = t_pintado − ts_mensaje − desfase, donde desfase = reloj del teléfono − reloj del
// servidor, estimado con el método de Cristian (hora del servidor + mitad del RTT). Como depende
// de esa estimación, se registra también lat_cliente = t_pintado − t_recepción, que no la necesita.

export interface Desfase {
  desfaseMs: number; // teléfono − servidor
  rttMs: number; // RTT de la muestra elegida (la de menor RTT)
  fuente: 'ts' | 'date'; // ts en ms del cuerpo de /salud, o el header Date (resolución de 1 s)
}

export interface Muestra {
  t_sim: number;
  lat_total_ms: number;
  lat_cliente_ms: number;
}

type Pedir = (url: string) => Promise<{ json(): Promise<unknown>; headers: { get(n: string): string | null } }>;

/** Cristian con `n` peticiones a /salud; se queda con la de menor RTT. */
export async function estimarDesfase(
  urlSalud: string,
  n = 5,
  pedir: Pedir = (u) => fetch(u, { cache: 'no-store' }),
  ahora: () => number = Date.now,
): Promise<Desfase> {
  let mejor: Desfase | null = null;
  for (let i = 0; i < n; i++) {
    const t0 = ahora();
    let r: Awaited<ReturnType<Pedir>>;
    try {
      r = await pedir(urlSalud);
    } catch {
      continue; // una petición fallida no descarta las demás muestras
    }
    const t1 = ahora();
    let servidor = NaN;
    let fuente: Desfase['fuente'] = 'ts';
    try {
      const cuerpo = (await r.json()) as { ts?: unknown };
      if (typeof cuerpo?.ts === 'string') servidor = Date.parse(cuerpo.ts);
    } catch {
      // sin cuerpo JSON
    }
    if (Number.isNaN(servidor)) {
      fuente = 'date';
      // El header Date trunca al segundo: se suma medio segundo para centrar el error.
      servidor = Date.parse(r.headers.get('date') ?? '') + 500;
    }
    if (Number.isNaN(servidor)) continue;
    const rtt = t1 - t0;
    const desfase = t1 - (servidor + rtt / 2);
    if (!mejor || rtt < mejor.rttMs) mejor = { desfaseMs: Math.round(desfase), rttMs: rtt, fuente };
  }
  if (!mejor) throw new Error('No se pudo estimar el desfase de reloj con /salud');
  return mejor;
}

/** Percentil por el método del rango más cercano (p en 0–100). */
export function percentil(valores: number[], p: number): number {
  if (valores.length === 0) return NaN;
  const orden = [...valores].sort((a, b) => a - b);
  const k = Math.max(1, Math.ceil((p / 100) * orden.length));
  return orden[k - 1];
}

export class RegistroLatencia {
  readonly muestras: Muestra[] = [];
  desfaseMs = 0;

  registrar(m: { t_sim: number; ts: string; recibidoEn: number; pintadoEn: number }): Muestra {
    const muestra = {
      t_sim: m.t_sim,
      lat_total_ms: Math.round(m.pintadoEn - Date.parse(m.ts) - this.desfaseMs),
      lat_cliente_ms: Math.round(m.pintadoEn - m.recibidoEn),
    };
    this.muestras.push(muestra);
    return muestra;
  }

  resumen() {
    const total = this.muestras.map((x) => x.lat_total_ms);
    const cliente = this.muestras.map((x) => x.lat_cliente_ms);
    return {
      n: this.muestras.length,
      total_p50: percentil(total, 50),
      total_p95: percentil(total, 95),
      cliente_p50: percentil(cliente, 50),
      cliente_p95: percentil(cliente, 95),
    };
  }

  aCSV(modo: string): string {
    const filas = this.muestras.map((x) => `${modo},${x.t_sim},${x.lat_total_ms},${x.lat_cliente_ms}`);
    return ['modo,t_sim,lat_total_ms,lat_cliente_ms', ...filas].join('\n') + '\n';
  }

  vaciar(): void {
    this.muestras.length = 0;
  }
}

/** Guarda el CSV en la caché y abre el menú de compartir del teléfono (expo-sharing). */
export async function exportarCSV(registro: RegistroLatencia, modo: string): Promise<string> {
  const { File, Paths } = await import('expo-file-system');
  const Sharing = await import('expo-sharing');
  const archivo = new File(Paths.cache, `latencias_espejo_${modo}_${Date.now()}.csv`);
  archivo.create();
  archivo.write(registro.aCSV(modo));
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(archivo.uri, { mimeType: 'text/csv', dialogTitle: 'Latencias del espejo' });
  }
  return archivo.uri;
}
