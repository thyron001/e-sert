"""Un router por recurso del contrato (§4.3). Todos se montan bajo `/api/v1`."""

from . import billetera, eventos, guia, puestos, sesiones, simulacion, sistema

ROUTERS = [sistema.router, puestos.router, guia.router, eventos.router, sesiones.router,
           billetera.router, simulacion.router]
