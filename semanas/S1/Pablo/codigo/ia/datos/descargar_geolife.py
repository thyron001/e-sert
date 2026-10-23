"""
Descarga el dataset GeoLife Trajectories 1.3 de Microsoft Research.
Idempotente: si el directorio de datos crudos ya tiene contenido, no descarga.
"""
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

URL_GEOLIFE = (
    "https://download.microsoft.com/download/F/4/8/"
    "F4894AA5-FDBC-481E-9285-D5F8C4C4F039/"
    "Geolife%20Trajectories%201.3.zip"
)

DIR_SCRIPT = Path(__file__).resolve().parent
DIR_CRUDOS = DIR_SCRIPT / "crudos"
DIR_ZIP = DIR_CRUDOS / "geolife.zip"
MARCA_EXTRACCION = DIR_CRUDOS / ".extraido"


def ya_descargado() -> bool:
    return MARCA_EXTRACCION.exists()


def descargar(url: str = URL_GEOLIFE) -> Path:
    DIR_CRUDOS.mkdir(parents=True, exist_ok=True)

    if ya_descargado():
        print("GeoLife ya descargado y extraído; omitiendo.")
        return DIR_CRUDOS

    print(f"Descargando GeoLife desde {url} ...")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    with open(DIR_ZIP, "wb") as f, tqdm(
        total=total, unit="B", unit_scale=True, desc="geolife.zip"
    ) as barra:
        for bloque in resp.iter_content(chunk_size=1 << 20):
            f.write(bloque)
            barra.update(len(bloque))

    print("Extrayendo...")
    with zipfile.ZipFile(DIR_ZIP, "r") as zf:
        zf.extractall(DIR_CRUDOS)

    DIR_ZIP.unlink()
    MARCA_EXTRACCION.touch()
    print(f"Extracción completa en {DIR_CRUDOS}")
    return DIR_CRUDOS


if __name__ == "__main__":
    descargar()
