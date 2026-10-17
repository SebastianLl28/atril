# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Atril arma paquetes de contexto para traducir y mejorar libros por partes. Se elige un rango de
páginas de un PDF **original** y, si se quiere, de una **referencia** (por ejemplo, una mala
traducción automática). Atril exporta un `contexto.md` con el texto ya limpio y fusionado, más
sus figuras. Después Claude Code procesa ese paquete con la skill `/libro` para producir el PDF
final. `PLAN.md` tiene las fases y su estado: leerlo antes de empezar trabajo nuevo.

**Restricción de diseño:** nada puede llamar a la API de Anthropic. La parte con IA ocurre
dentro de Claude Code (skill `/libro`, con la suscripción del usuario). Todo lo mecánico va en
código determinista, para gastar menos del plan.

## Comandos

```fish
uv sync                                        # instalar dependencias
uv run pytest                                  # todos los tests
uv run pytest tests/test_parte_iii.py::test_salen_las_20_figuras   # un test
uv run atril --help                            # CLI: nuevo | proyectos | indice | mapa | exportar
                                               #      iniciar | construir | ver (salida a PDF) | app
                                               #      ocr | imprimir (--simular: no imprime)
```

`tests/test_parte_iii.py` usa los PDFs reales de `~/Documents/books` (Arquitectura Limpia) y
se salta si no están (igual que el test app = CLI de `tests/test_app.py`);
`tests/test_salida.py` y el resto de `test_app.py` no necesitan los PDFs. El nombre del PDF en español usa una «ñ» descompuesta (NFD): buscarlo con glob
(`Espa*l.pdf`), no con el nombre literal.

## Arquitectura

Flujo: `pdf.Libro` → `limpieza.limpiar` → `paquete.exportar` → `contexto.md`, con
`mapa` y `proyecto` alrededor.

- **`pdf.py`**: convierte cada página en una lista de `Elemento` (titulo, subtitulo, parrafo,
  cita, codigo, vineta, pie_figura, imagen), ordenados por posición vertical.
  - La clasificación es **relativa al tamaño de letra del cuerpo** (`tamano_cuerpo`, el más
    usado en una muestra del libro), no a tamaños absolutos.
  - Las fuentes monoespaciadas marcan código: si todo el bloque es mono, es un bloque de
    código; si son fragmentos dentro de prosa, quedan como `` `código` ``.
  - Las imágenes que cubren más del 80 % de la página se descartan: son escaneos, como cada
    página del PDF en español, no figuras.
- **`limpieza.py`**: quita marcas fijas (`MARCAS`, más `limpieza.marcas` de libro.json), los
  encabezados y pies repetidos en la franja superior o inferior de la página y los números de
  página. Después `fusionar` reconstruye los párrafos partidos línea a línea (el PDF escaneado
  trae un bloque por línea) y une el código consecutivo.
- **`mapa.py`**: empareja cada página de la referencia con una del original, sin IA.
  - Usa como anclas las palabras idénticas en ambos idiomas, ponderadas por idf, y los números
    de figura.
  - Una programación dinámica monótona elige el camino: la página del original avanza 0–2 por
    cada página de la referencia.
  - Las anclas manuales (`atril mapa --ancla REF=ORIG`) fuerzan el camino. Se guardan en
    `libro.json` y el mapa completo se recalcula.
- **`proyecto.py`**: la carpeta de cada libro vive **fuera del repo**, en
  `~/Documents/books/proyectos/<slug>/` (se cambia con `ATRIL_PROYECTOS`). Contiene:
  - `libro.json`: rutas de los PDFs, idiomas, mapa, anclas y partes exportadas;
  - `glosario.md`: lo actualiza la skill y se copia en cada exportación nueva;
  - una carpeta por parte.
- **`paquete.py`**: con un solo rango basta; el otro se deduce del mapa. Escribe:
  - `<parte>/contexto.md`: cabecera YAML con las rutas absolutas a los PDFs originales como
    respaldo, instrucciones, glosario, índice de la parte y un `## Bloque` por página del
    original con sus páginas de referencia agrupadas;
  - `<parte>/figuras/`: las imágenes en su formato original, llamadas `fig-7.1` si tienen pie
    de figura o `ilus-pNNN-k` si no.
  
  La skill `/libro` consume este formato: si se cambia, hay que actualizar ambos.
- **`construir.py`** + **`plantilla/`** (`libro.css`, `base.html`): todo en `<parte>/salida/`.
  `iniciar` crea `<parte>.html` desde la plantilla. `construir` copia `libro.css`, genera el
  PDF (WeasyPrint), el 2 por hoja (pypdf) y las miniaturas `revision/hoja-NN.png` (PyMuPDF), y
  marca la parte `construida`. Los ajustes de una parte van en un `<style>` de su HTML, no en
  `libro.css`.
- **`svg.py`**: librería de diagramas (`Svg` con `cls`, `arrow`, `actor`, `component`…). Cada
  parte la usa desde su `salida/figs.py`.
- **`app.py`** + **`web/`** + **`miniaturas.py`**: la app visual (`atril app`). `crear_app(raiz,
  libros, cache)` arma la FastAPI. Guarda en memoria un `Proyecto` abierto por slug y protege
  PyMuPDF con un candado, porque no es seguro entre hilos. El frontend es HTML + JS sin build.
  `web/app.js` repite en JS `rango_original` y `rango_referencia` de `mapa.py`: si cambian,
  hay que cambiar los dos. Los textos de página se cachean en `Libro.textos`.
- **`ocr.py`**: `necesita_ocr` mira una muestra de páginas y `ocr` llama a ocrmypdf
  (`uv tool install ocrmypdf`). **`imprimir.py`**: `lp` a la impresora predeterminada (Epson
  L3250) o a `ATRIL_IMPRESORA`. **Nunca imprimir de verdad en pruebas**: usar `--simular` o el
  `lp` falso de `tests/test_fase4.py`.
- **Índice detectado** (`Libro.indice_detectado`): si el PDF no trae TOC, salen títulos por
  tamaño relativo al cuerpo. Las páginas con número de capítulo muy grande (≥ 2,3×) son
  capítulos.
- **`.claude/skills/libro/SKILL.md`**: la skill `/libro`, con los pasos y las reglas de estilo
  sacadas del caso SOLID.

`referencia/solid/` es el caso hecho a mano (Parte III, principios SOLID): `solid.html` y
`figs.py`, que usa `atril.svg`. Es el modelo de estilo de la skill y la regresión de la
plantilla: compilado con `libro.css` debe dar las mismas 32 páginas. Si se toca `libro.css` o
`svg.py`, `tests/test_salida.py` lo comprueba. `en-p62-86.txt` es la referencia que usan
los tests para comprobar que el texto extraído está completo.

## Convenciones

El código, los nombres y los mensajes están en español, igual que la conversación con el
usuario.
