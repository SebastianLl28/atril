# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Atril prepara documentos (libros, informes, apuntes) para leerlos y estudiarlos mejor, por
partes. Se elige un rango de páginas de un PDF con texto (el **documento**, `original` en el
código) y, si se quiere, de **otra versión** en otro idioma (`referencia` en el código y en
`libro.json`). En cada parte se decide la **tarea**:
- traducir o mantener el idioma;
- mejorar la lectura;
- comentarios, contexto, resumen.

Se pueden sumar **fuentes adicionales**: notas, enlaces y páginas de otros PDFs. Atril exporta
un `contexto.md` con el texto ya limpio y fusionado, más sus figuras. **No traducir no es un caso
raro**: el idioma de salida por defecto es el del documento. No se aceptan PDFs que son solo
imágenes (`pdf.solo_imagenes`); no hay OCR.

Después Claude Code procesa ese paquete con la skill `/libro` para producir el PDF final.
`PLAN.md` tiene las fases y su estado: leerlo antes de empezar trabajo nuevo.

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
                                               #      imprimir (--simular: no imprime)
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
    respaldo, `tarea` e `idioma_salida`. Después, las secciones `# Tarea` (en palabras),
    `# Instrucciones`, `# Glosario`, `# Índice de la parte`, `# Fuentes adicionales` (notas,
    enlaces y el texto limpio de otros PDFs) y `# Contenido`, con un `## Bloque` por página
    del documento y sus páginas de la otra versión agrupadas;
  - `<parte>/figuras/`: las imágenes en su formato original, llamadas `fig-7.1` si tienen pie
    de figura o `ilus-pNNN-k` si no. Las de la otra versión llevan el prefijo `ref-` y las de
    los PDFs de apoyo, `fuenteN-`.

  `paquete.TAREA` define los campos de la tarea; la app (`app.Tarea`), la CLI y la portada
  (`construir._textos_portada`) la siguen.
  
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
- **`imprimir.py`**: `lp` a la impresora predeterminada (Epson
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
