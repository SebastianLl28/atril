# Atril · plan: traductor y potenciador de libros por partes

Herramienta personal para elegir páginas de un libro (y, si se quiere, de su versión en otro
idioma), generar un paquete de contexto ya fusionado y pasárselo a Claude Code para producir
un PDF imprimible: traducción revisada, diagramas redibujados y comentarios de estudio.

**Restricción:** nada usa la API de pago. La parte con IA la hace Claude Code (suscripción)
mediante la skill `/libro`; todo lo mecánico lo hacen scripts, para gastar menos del plan.

## Arquitectura

```
App selectora (sin IA)  ──►  paquete de la parte  ──►  Claude Code /libro  ──►  PDF (1 y 2 por hoja)
miniaturas, índice,          contexto.md fusionado     traduce, redibuja,       WeasyPrint + pypdf,
búsqueda, mapa ES↔EN         + figuras/                comenta, revisa          miniaturas de revisión
```

| Parte | Qué hace | Costo |
|---|---|---|
| App + núcleo (Python) | leer PDFs, emparejar páginas, limpiar texto, extraer figuras, escribir el paquete | gratis |
| Scripts de salida | HTML → PDF, 2 por hoja, hoja de miniaturas para revisar | gratis |
| Skill `/libro` en Claude Code | traducir, redibujar diagramas en SVG, comentarios, glosario | suscripción |

### Decisiones tomadas

- **Todo en Python.** El backend usa FastAPI y el frontend es HTML + JS sin paso de build.
  PyMuPDF genera miniaturas, índice, texto y figuras, así que no hace falta PDF.js ni Node.
- **El código va en `~/Projects/atril`** y los proyectos de cada libro en
  `~/Documents/books/proyectos/<libro>/`, junto a los PDFs.
- **La skill va dentro del proyecto** (`.claude/skills/libro/`), versionada con git. Para
  usarla se abre `claude` en `~/Projects/atril`.
- **El paquete trae el texto ya fusionado**, no los PDFs. Leer texto limpio cuesta mucho
  menos que leer páginas de PDF, que se procesan como imagen. Las rutas a los PDFs originales
  y sus rangos van en el encabezado, como respaldo: si una página se extrajo mal, se lee esa
  página del original.
- **El modo de un solo PDF existe desde el principio.** El PDF de referencia es opcional; por
  ejemplo, para mejorar la lectura del JWT Handbook o del Curso Linux.

## Formatos

### Carpeta del libro

```
~/Documents/books/proyectos/arquitectura-limpia/
  libro.json          ← fuentes, roles, mapa de páginas ES↔EN, partes hechas
  glosario.md         ← decisiones de términos; se acumula de una parte a otra
  parte-03-solid/
    contexto.md       ← lo único que lee Claude al empezar
    figuras/          ← figuras originales en su formato: fig-7.1.jpeg, ilus-p064-1.jpeg…
    salida/           ← lo que genera la skill: html, svg, pdf, pdf 2 por hoja, revisión
```

### `libro.json`

```json
{
  "titulo": "Arquitectura Limpia",
  "fuentes": {
    "en": { "pdf": "/home/sebastianll/Documents/books/Arquitectura Limpia - ingles.pdf",
            "idioma": "en", "rol": "original" },
    "es": { "pdf": "/home/sebastianll/Documents/books/Arquitectura Limpia - Español.pdf",
            "idioma": "es", "rol": "referencia" }
  },
  "mapa": { "anclas_manuales": { "77": 62, "108": 86 }, "es_a_en": [1, 1, 2, "…"] },
  "partes": [
    { "id": "parte-03-solid", "en": "62-86", "es": "77-108", "estado": "terminada" }
  ]
}
```

### `contexto.md`

```markdown
---
libro: Arquitectura Limpia
parte: III · Principios de diseño (cap. 7–11)
paquete: /home/sebastianll/Documents/books/proyectos/arquitectura-limpia/parte-03-solid
original:   { pdf: "/home/…/Arquitectura Limpia - ingles.pdf", idioma: en, paginas: 62-86 }
referencia: { pdf: "/home/…/Arquitectura Limpia - Español.pdf", idioma: es, paginas: 77-108,
              nota: "traducción automática con errores; solo como apoyo" }
idioma_destino: es
salida: [carta, 2-por-hoja]
estadisticas: { paginas_en: 25, paginas_es: 32, palabras: 19800, figuras: 20 }
---

# Instrucciones
(lo que se escribió en la caja de texto de la app)

# Glosario del libro
(copiado de glosario.md al momento de exportar)

# Contenido

## Bloque 1 · EN p.62 ↔ ES p.77–78
### EN · original
texto limpio, con párrafos reconstruidos…
### ES · referencia
texto limpio…
### Figuras
![Ilustración del capítulo](figuras/ilus-parte3.png)

## Bloque 2 · EN p.63 ↔ ES p.79
…
```

La limpieza quita marcas como «Machine Translated by Google» y «Click here to view code image»,
además de los encabezados y pies que se repiten en cada página. También une las palabras
cortadas con guion y reconstruye los párrafos a partir de los bloques de PyMuPDF.

## Fases

### Fase 0 · Base del proyecto ✅
- [x] Rescatar el SOLID de `/tmp` → `referencia/solid/` (HTML, CSS, figs.py, SVG, ilustraciones)
- [x] Prototipo de emparejamiento → integrado en `src/atril/mapa.py`
- [x] `uv init` con el paquete `atril` y las dependencias pymupdf, weasyprint, pypdf y
      pillow; pytest para desarrollo
- [x] `git init` y `.gitignore`

**Verificación:** compilar `referencia/solid/solid.html` con la WeasyPrint del proyecto debe
dar las mismas 32 páginas. Eso confirma que las fuentes y la plantilla funcionan fuera de `/tmp`.

### Fase 1 · Núcleo: del PDF al paquete (sin IA) ✅
- `src/atril/pdf.py`: abrir, índice (TOC), texto por página, figuras con posición y pie de figura
- `src/atril/limpieza.py`: reglas de limpieza; cada libro puede agregar las suyas
- `src/atril/mapa.py`: emparejar ES↔EN por anclas (identificadores, siglas, «Figura 8.2») con
  programación dinámica monótona. Las correcciones manuales quedan como anclas fijas.
- `src/atril/paquete.py`: escribir `contexto.md` + `figuras/` y registrar la parte en `libro.json`
- `src/atril/cli.py`: `atril nuevo`, `atril mapa`, `atril exportar`, `atril indice`

**Verificación**, con tests sobre la Parte III:
- el texto EN coincide con `referencia/solid/en-p62-86.txt`;
- salen las 20 imágenes (14 diagramas y 6 ilustraciones);
- el mapa da 77→62 y 108→86, a ±1 página antes de corregir;
- el paquete no contiene «Machine Translated».

### Fase 2 · Skill `/libro` y salida a PDF (la parte con IA) ✅
- [x] `src/atril/plantilla/libro.css` + `base.html`, sacados de `solid.html`: portada, índice
      con números de página, capítulos, figuras, recuadros COMENTARIO, notas al pie.
      `atril iniciar <carpeta>` crea `salida/<parte>.html` desde la plantilla, con lo que se
      sabe sin IA (libro, parte, páginas) ya puesto.
- [x] `src/atril/svg.py`: `figs.py` convertido en librería (clases UML, flechas de uso y de
      implementación, componentes, actores, procesos, almacenes). `referencia/solid/figs.py`
      ya la usa y genera los mismos SVG byte a byte.
- [x] `src/atril/construir.py`, que se ejecuta con `atril construir <carpeta>`:
  - HTML → PDF con WeasyPrint;
  - 2 por hoja con pypdf (misma geometría que el PDF del SOLID);
  - hojas de miniaturas (`salida/revision/hoja-NN.png`) con PyMuPDF; `atril ver` renderiza
    páginas sueltas en detalle;
  - marca la parte como `construida` en `libro.json`.
- [x] `.claude/skills/libro/SKILL.md`: reglas de traducción y comentarios del caso SOLID. Pasos:
  1. leer `contexto.md`;
  2. confirmar el plan con el usuario;
  3. traducir capítulo por capítulo;
  4. redibujar los diagramas;
  5. escribir los comentarios;
  6. `atril construir`;
  7. revisar las miniaturas y corregir;
  8. actualizar `glosario.md`.

**Verificación:**
- [x] recompilar el SOLID con `libro.css` y que se vea igual: 32 páginas, sin diferencias de
  píxeles con el PDF hecho a mano (`tests/test_salida.py`);
- [x] procesar de punta a punta un capítulo corto nuevo de la Parte IV y revisar que el estilo
  coincida y que `glosario.md` se haya actualizado: el cap. 12 (EN 88–92) da 9 páginas y
  `glosario.md` queda con 20 términos.

### Fase 3 · App visual
- Miniaturas de página con PyMuPDF (con caché).
- Backend FastAPI dentro del mismo paquete. Lista los PDFs de `~/Documents/books` y sirve el
  proyecto, miniaturas y vistas grandes con caché, índice, búsqueda, mapa y exportación.
- Frontend:
  - dos paneles lado a lado con miniaturas que cargan al hacer scroll;
  - selección con clic y shift+clic, o por capítulo desde el índice;
  - una búsqueda que marca las páginas donde aparece el término;
  - al elegir páginas en un panel se marca el rango que corresponde en el otro, se puede
    ajustar y el ajuste se guarda como ancla;
  - caja de instrucciones con plantillas: traducir y revisar, solo mejorar la lectura…;
  - contador de páginas y palabras, con aviso si la parte es demasiado grande (más de unas
    35 páginas);
  - botón Exportar, que muestra la ruta del paquete y el comando `/libro <ruta>` listo para
    copiar.
- Se abre con `uv run atril app`.

**Verificación:** exportar la Parte III desde la app debe dar el mismo paquete que la línea
de comandos (diff).

### Fase 4 · Mejoras, cuando hagan falta
- OCR automático para PDFs sin capa de texto (`uv tool install ocrmypdf`; tesseract con spa y
  eng ya está instalado)
- Detectar títulos de capítulo en PDFs sin índice, por tamaño de letra
- Botón para imprimir con `lp` en la Epson L3250
- Historial de partes en la app, con su estado y enlace al PDF

## Referencias
- Caso real: `referencia/solid/` y `~/Documents/books/Arquitectura Limpia - SOLID (español revisado).pdf`
- Prueba de emparejamiento sin IA: Parte III con error de ±1 página (ES 77→63, real 62;
  ES 108→85, real 86). La única dependencia es la librería estándar de Python.
