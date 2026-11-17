"""Arreglos de los criterios pendientes de S2-3, hechos en S4 (sin SUMO).

- Cortacircuitos del `Publicador`: con el backend caído, `listo()` deja de pedir cuerpos salvo
  una sonda cada `pausa_caido_s`, y vuelve a True con la primera respuesta buena.
- `liquidar_al_final`: cierra las sesiones abiertas con motivo `manual`; la retención queda en 0 y
  el libro cuadra.
"""

import socket
import time

from traci.clasificacion import buscar_proyecto
from traci.correr_guiado import libro_cuadra, liquidar_al_final
from traci.puente_nucleo import Publicador, PuenteNucleo


def _puerto_cerrado() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]  # al salir del with nadie escucha: conexión rechazada


def test_cortacircuitos_con_backend_caido():
    pub = Publicador(f"http://127.0.0.1:{_puerto_cerrado()}", timeout_s=0.2, reintentos=1, backoff_s=0.01,
                     pausa_caido_s=0.5)
    assert pub.listo()
    pub.publicar({"t_sim": 1.0})
    fin = time.monotonic() + 5
    while not pub.caido and time.monotonic() < fin:
        time.sleep(0.01)
    assert pub.caido and pub.fallidos == 1
    assert not pub.listo()            # no se arman cuerpos mientras está caído…
    time.sleep(0.55)
    assert pub.listo()                # …salvo una sonda cada pausa_caido_s
    assert not pub.listo()
    pub.cerrar(espera_s=0.1)


def test_liquidar_al_final_deja_retencion_cero_y_libro_cuadrado():
    puente = PuenteNucleo(buscar_proyecto() / "sumo" / "parqueos" / "puestos.csv", semilla=1)
    pid = next(iter(puente.mapa.puestos))
    for i in range(3):
        puente.registrar(f"sim_veh{i}")
        puente.iniciar(f"sim_veh{i}", pid, t_sim=10.0 * i)
    sid = next(iter(puente.abiertas))
    puente.transicion(sid, "SALIENDO", 700.0)
    puente.cerrar(sid, 700.0)
    assert len(puente.abiertas) == 2
    assert liquidar_al_final(puente, 1800.0) == 2
    assert not puente.abiertas
    assert sum(f["retencion_neta_centavos"] for f in puente.libro().values()) == 0
    assert [f["motivo"] for f in puente.cerradas] == ["deteccion", "manual", "manual"]
    assert libro_cuadra(puente)
