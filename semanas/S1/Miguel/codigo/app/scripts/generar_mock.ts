// Imprime el recorrido mock del espejo como JSON (lo redirige `npm run generar-mock`).
// El servidor mock de S2-3 reproducirá src/espejo/recorrido_mock.json tal cual.
import { generarRecorrido } from '../src/espejo/recorridoMock';

console.log(JSON.stringify(generarRecorrido('sim_veh42'), null, 2));
