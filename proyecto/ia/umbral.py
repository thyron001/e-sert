"""
Clasificador por umbral de velocidad (línea base del contrato §2).

vel_media > 8 km/h (2.222 m/s) -> vehiculo
vel_media < 0.5 km/h (0.139 m/s) -> quieto
resto -> a_pie
"""

UMBRAL_VEHICULO_MPS = 8.0 / 3.6   # 2.222 m/s
UMBRAL_QUIETO_MPS = 0.5 / 3.6     # 0.139 m/s


def clasificar_umbral(vel_media: float) -> str:
    if vel_media > UMBRAL_VEHICULO_MPS:
        return "vehiculo"
    if vel_media < UMBRAL_QUIETO_MPS:
        return "quieto"
    return "a_pie"


def predecir_lote(vel_medias):
    """Aplica la regla de umbral a un array/serie de velocidades medias."""
    return [clasificar_umbral(v) for v in vel_medias]
