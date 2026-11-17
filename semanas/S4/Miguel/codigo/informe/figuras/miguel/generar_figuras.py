"""Regenera las figuras de la sección de la app (informe/miguel.md) a partir de las capturas y evidencias.

Uso (desde semanas/S4/Miguel/codigo/): python informe/figuras/miguel/generar_figuras.py
Copia las capturas a 300 dpi y arma la tira de pantallas. Necesita Pillow.
"""
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
CODIGO = AQUI.parents[2]
EVID = CODIGO.parent / "evidencias"

COPIAS = {
    "m09_ensayo.png": EVID / "s2_ensayo-montaje.png",
    "m10_recibo-ensayo.png": EVID / "s2_recibo-ensayo.png",
}


def tira(nombres: list[str], salida: Path, alto: int = 1200) -> None:
    ims = [Image.open(CODIGO / n).convert("RGB") for n in nombres]
    ims = [i.resize((int(i.width * alto / i.height), alto)) for i in ims]
    m = 24
    out = Image.new("RGB", (sum(i.width for i in ims) + m * (len(ims) + 1), alto + 2 * m), "white")
    x = m
    for i in ims:
        out.paste(i, (x, m))
        x += i.width + m
    out.save(salida, dpi=(300, 300))


def main() -> None:
    for nombre, origen in COPIAS.items():
        Image.open(origen).convert("RGB").save(AQUI / nombre, dpi=(300, 300))
    tira(["app/capturas/01_inicio.png", "app/capturas/02_mapa.png", "app/capturas/06_aviso.png",
          "app/capturas/07_recibo.png", "app/capturas/08_billetera.png"], AQUI / "m00_pantallas.png")
    tira(["app/capturas/03_selector.png", "app/capturas/04_espejo_guiado.png", "app/capturas/05_espejo_apie.png"],
         AQUI / "m05_espejo.png")


if __name__ == "__main__":
    main()
