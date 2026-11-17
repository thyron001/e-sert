"""Capa HTTP y WebSocket del backend (FastAPI) sobre `backend/nucleo/`.

Regla: aquí no hay reglas de cobro ni de ocupación. Cada ruta valida con los modelos de
`comun/esquemas.py`, llama al núcleo y traduce sus errores (`errores.py`).
"""
