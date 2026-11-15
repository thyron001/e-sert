// Comprueba que las copias del contrato en src/contrato/ son idénticas a las de comun/.
// Uso: npm run verificar-contrato   (sale con código 1 si algo difiere o no hay original).
//
// - esquemas.ts: la copia lleva una primera línea de cabecera ("// Copia de comun/ ...") que
//   se quita antes de calcular el hash.
// - tarifa.json: copia byte a byte (JSON no admite comentarios).
// Los finales de línea CRLF se normalizan a LF para que en Windows dé lo mismo.
//
// Dónde busca el original: la variable CONTRATO_ORIGEN si existe; si no, ../comun (estructura
// tras la unificación: proyecto/app + proyecto/comun) y, si tampoco, sube desde la app hasta
// encontrar una carpeta con proyecto/comun/esquemas.ts.

import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const COPIAS = path.join(APP, 'src', 'contrato');
const CABECERA = '// Copia de comun/';

function buscarOrigen() {
  if (process.env.CONTRATO_ORIGEN) return path.resolve(process.env.CONTRATO_ORIGEN);
  const hermano = path.resolve(APP, '..', 'comun');
  if (existsSync(path.join(hermano, 'esquemas.ts'))) return hermano;
  let dir = APP;
  while (true) {
    const candidato = path.join(dir, 'proyecto', 'comun');
    if (existsSync(path.join(candidato, 'esquemas.ts'))) return candidato;
    const padre = path.dirname(dir);
    if (padre === dir) return null;
    dir = padre;
  }
}

const leerTexto = (ruta) => readFileSync(ruta, 'utf8').replace(/\r\n/g, '\n');
const sha = (texto) => createHash('sha256').update(texto, 'utf8').digest('hex');

function sinCabecera(texto, ruta) {
  const salto = texto.indexOf('\n');
  const primera = salto === -1 ? texto : texto.slice(0, salto);
  if (!primera.startsWith(CABECERA)) {
    console.error(`AVISO: ${ruta} no empieza con la cabecera "${CABECERA} ..."`);
    return texto;
  }
  return salto === -1 ? '' : texto.slice(salto + 1);
}

const origen = buscarOrigen();
if (!origen || !existsSync(origen)) {
  console.error('ERROR: no se encontró el original del contrato (comun/esquemas.ts).');
  console.error('Define CONTRATO_ORIGEN con la carpeta comun/ o ejecuta desde el repo.');
  process.exit(1);
}
console.log(`Original: ${origen}`);

const ARCHIVOS = [
  { nombre: 'esquemas.ts', copia: (t, r) => sinCabecera(t, r) },
  { nombre: 'tarifa.json', copia: (t) => t },
];

let fallos = 0;
for (const { nombre, copia } of ARCHIVOS) {
  const rutaCopia = path.join(COPIAS, nombre);
  const rutaOriginal = path.join(origen, nombre);
  if (!existsSync(rutaCopia) || !existsSync(rutaOriginal)) {
    console.log(`FALTA   ${nombre}  ${existsSync(rutaCopia) ? 'original' : 'copia'} no existe`);
    fallos++;
    continue;
  }
  const hCopia = sha(copia(leerTexto(rutaCopia), rutaCopia));
  const hOriginal = sha(leerTexto(rutaOriginal));
  if (hCopia === hOriginal) {
    console.log(`OK      ${nombre}  ${hCopia.slice(0, 12)}`);
  } else {
    console.log(`DIFIERE ${nombre}  copia ${hCopia.slice(0, 12)} ≠ original ${hOriginal.slice(0, 12)}`);
    fallos++;
  }
}

if (fallos) {
  console.error(`${fallos} archivo(s) del contrato no coinciden: copia de nuevo desde ${origen}.`);
  process.exit(1);
}
