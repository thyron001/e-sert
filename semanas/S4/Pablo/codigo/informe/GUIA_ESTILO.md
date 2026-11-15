# Guía de estilo del informe e-sert

Todas las secciones se escriben igual para que `construir_informe.py` las una sin retoques.
Cada persona escribe **solo** su archivo (`tyrone.md`, `freddy.md`, `pablo.md`, `miguel.md`) y sus
figuras. Pablo (editor) escribe las partes comunes y el armado.

## Estructura

- **Una sección por archivo.** El archivo empieza con un título de nivel 2 (`## Inteligencia artificial`)
  y usa `###` para las subsecciones. Nunca un título de nivel 1 (`#`): el título del informe es del maestro.
- **No numeres a mano** secciones, figuras ni tablas: el armador las numera y reescribe las referencias.
- Longitud objetivo: **1 500 a 2 500 palabras** por sección (el verificador exige al menos 800).
- Idioma: español. Coma decimal (`0,87`), espacio como separador de miles (`294 579`), `%` pegado al
  número con espacio (`96,2 %`). Los identificadores de código y las rutas van entre comillas invertidas.

## Figuras

- Las imágenes viven en `informe/figuras/<nombre>/` (`<nombre>` en minúscula: `tyrone`, `freddy`, `pablo`,
  `miguel`) y se enlazan con **ruta relativa al archivo de la sección**:
  `![](figuras/pablo/f01_importancia.png)`.
- El texto alternativo va vacío y el **pie de figura va justo debajo, en cursiva**, en una línea:

  ```markdown
  ![](figuras/pablo/f01_importancia.png)
  *Importancia por permutación de las características en usuarios no vistos.*
  ```

  El armador antepone "Figura N." al pie.
- PNG a 300 dpi con ejes y leyendas en español. Cada figura tiene que poder regenerarse con un script.

## Tablas

- Tablas en Markdown, con el pie en cursiva **justo encima**: `*Ventanas por clase y fuente.*`
  (el armador antepone "Tabla N."). Alinea las columnas numéricas a la derecha (`---:`).

## Citas

- Se cita con `[@clave]` (varias: `[@clave1; @clave2]`). Toda clave debe existir en `informe/referencias.bib`.
  Si no puedes comprobar una referencia (autores, año, revista, DOI), **no la pongas**.

## Trazabilidad de cifras

- Cada cifra de resultado lleva un comentario `<!-- fuente: ruta -->` en el mismo párrafo o tabla, o en
  la línea del pie que la precede. La ruta es relativa a `codigo/` de la persona (o a la raíz del repo) y
  puede apuntar a una clave: `<!-- fuente: ia/modelos/rf_final.json:metricas.f1_macro -->`.
- Si varias secciones usan la **misma métrica**, deben citar la **misma fuente** y dar el mismo valor: el
  verificador compara los valores que apuntan a la misma fuente.
- Los parámetros y definiciones que no son resultados (`30 s`, `8 km/h`) van entre comillas invertidas.

## Texto final

- El documento entregado **no puede contener** `TODO`, `PENDIENTE` ni `MOCK`. Mientras falte una cifra de otra
  persona se escribe `[PENDIENTE: ...]` en el borrador, se anota el pedido en la bitácora y se quita antes de
  la entrega. Nunca se inventa una cifra.
- Los comentarios HTML `<!-- ... -->` no se ven en el PDF y son parte de la trazabilidad: no los borres.

## Plantilla mínima

```markdown
## Mi sección

Texto con una cifra: la métrica vale 0,87 [@breiman2001random]. <!-- fuente: ia/modelos/rf_final.json:metricas.f1_macro -->

*Resultados por fuente.*

| Fuente | F1 macro |
|---|---:|
| Prueba | 0,87 |

<!-- fuente: ia/modelos/rf_final.json:metricas.f1_macro -->

![](figuras/pablo/f01_ejemplo.png)
*Pie de la figura.*
```
