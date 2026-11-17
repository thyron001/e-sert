## Glosario

- **Falsa liberación:** cerrar la sesión de parqueo, y ofrecer el puesto a otros, mientras el auto sigue estacionado.
- **Retardo de cierre:** tiempo entre la salida real del auto y el cierre de la sesión.
- **Contrato (§2, §3):** el documento del proyecto que fija los modos de movimiento, la máquina de estados de la sesión y la API.
- **Teléfono espejo:** teléfono que, en vez de enviar su propio GPS, sigue a un auto simulado y muestra lo que vería su conductor.
- **Ventana:** tramo de 30 s de GPS a 1 Hz sobre el que se clasifica el movimiento, con paso de 5 s.
- **F1 macro:** promedio del F1 (equilibrio entre precisión y *recall*) de las tres clases; 1 es perfecto.
- **Ruido AR(1):** error de posición que se parece al del instante anterior; `σ` es su tamaño típico en metros.
- **Bootstrap agrupado:** forma de medir la incertidumbre remuestreando usuarios o sesiones completos, no ventanas sueltas.
- **GroupKFold:** validación que deja todas las ventanas de un usuario del mismo lado.
- **Penetración de la app:** porcentaje de conductores que usan la aplicación en una simulación.
