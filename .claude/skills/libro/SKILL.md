---
name: libro
description: Procesa una parte de un documento (libro, informe, apuntes) a partir de un paquete de Atril (contexto.md + figuras/). Según la tarea del paquete, transcribe o traduce, mejora la lectura, agrega comentarios y contexto con fuentes adicionales, y produce el PDF imprimible. Usar cuando el usuario escribe /libro <carpeta-de-la-parte> o pide procesar un paquete exportado con Atril.
argument-hint: <carpeta de la parte, la que tiene contexto.md>
---

# /libro: de un paquete de Atril al PDF final

Paquete: `$ARGUMENTS` (si viene vacío, pregunta la ruta o usa la última parte con
`uv run atril proyectos`). Trabaja desde `~/Projects/atril`: todos los comandos son
`uv run atril …`.

**No siempre hay que traducir.** Lo que se hace lo decide la `tarea` de la cabecera de
`contexto.md` (y su sección `# Tarea`):

| Campo | Si está activo |
|---|---|
| `traducir: "es"` | traducir a ese idioma; con `null`, **mantener el idioma** y transcribir fiel |
| `mejorar_lectura` | maquetación cuidada y diagramas redibujados en SVG; si no, texto con las figuras originales |
| `comentarios` | recuadros de estudio que explican lo difícil |
| `contexto` | recuadros con antecedentes, apoyados en las fuentes adicionales |
| `resumen` | resumen final de repaso |

Las instrucciones del usuario mandan sobre todo lo demás. El caso modelo de estilo es
`referencia/solid/solid.html` (traducción, comentarios y resumen del SOLID). Ante cualquier
duda de maquetación, imita lo que hace ese archivo: busca el patrón con grep en lugar de
leerlo entero.

## Ahorro de plan

- `contexto.md` es lo único que se lee entero. Ya trae el texto limpio y fusionado, y las
  fuentes adicionales en PDF ya extraídas.
- Los PDFs (rutas en la cabecera) se abren solo si un bloque se ve mal extraído: texto
  cortado, columnas mezcladas o una figura que falta. Lee únicamente esa página.
- La **otra versión** (si hay) es una ayuda: sirve para ver cómo se tradujo un término, pero
  **no se copia**. Suele ser una traducción automática con errores.
- Los **enlaces** de las fuentes se consultan solo si hay `contexto` o comentarios que los
  necesiten. Lee cada enlace una vez y quédate con lo pertinente.
- Para revisar la maqueta, mira primero las hojas de miniaturas. Usa `atril ver` solo para
  las páginas con algún problema.

## Pasos

### 1. Leer el paquete
Lee `<carpeta>/contexto.md`. Fíjate en:
- `tarea` e `idioma_salida`;
- las instrucciones;
- el glosario acumulado;
- el índice de la parte (puede no haber: los informes y PDFs sin índice se organizan por sus
  propios títulos);
- `# Fuentes adicionales`: notas, enlaces y páginas de otros PDFs.

Lista `<carpeta>/figuras/`.

### 2. Confirmar el plan con el usuario (una sola pregunta)
Presenta en pocas líneas:
- qué vas a hacer según la tarea, dicho en lenguaje llano («transcribir en inglés, mejorar la
  lectura y agregar contexto con los 2 enlaces», por ejemplo);
- las secciones o capítulos y las páginas que ocupan;
- las figuras: cuáles se redibujan en SVG y cuáles se conservan como imagen;
- si se traduce, los términos dudosos que aún no están en el glosario, con tu propuesta;
- dónde irán los comentarios y el contexto, y de qué fuente sale cada recuadro de contexto;
- cualquier cosa rara del paquete: páginas vacías, texto mal extraído, un enlace que no carga.

Espera la respuesta antes de escribir.

### 3. Escribir el texto, sección por sección
Ejecuta `uv run atril iniciar <carpeta>`. Crea `salida/<parte>.html` desde la plantilla, con
la portada ya ajustada a la tarea, y deja marcado con `COMPLETAR` lo que falta. Sustituye la
sección de ejemplo por las reales y agrega cada una al HTML apenas la termines, con Edit.
No acumules todo para el final.

**Fidelidad, siempre:** frase por frase, sin resumir, sin omitir párrafos ni notas al pie y
sin añadir nada fuera de los recuadros de comentario o contexto.

- **Si se traduce:** sigue «Traducción» más abajo y el glosario. Anota las decisiones nuevas
  para el paso 8.
- **Si se mantiene el idioma:** transcribe el texto tal cual. Solo corrige lo que rompió la
  extracción del PDF: palabras partidas o pegadas, ligaduras, guiones de corte, párrafos
  cortados o listas deshechas. No reescribas, no «mejores» la redacción y no cambies la
  ortografía del autor. Los recuadros que agregues van en el idioma del documento.

**Documentos sin capítulos** (informes, artículos): un `<section class="cap">` por cada
sección grande, numeradas como en el original, o una sola si el documento es corto. El
índice de la portada solo si hay dos secciones o más.

### 4. Figuras
**Con `mejorar_lectura`:** redibuja cada diagrama de `figuras/` (mira la imagen):
- Escribe su código en `salida/figs.py` con la librería `atril.svg`. Usa
  `referencia/solid/figs.py` como modelo de API y de medidas.
- Ejecuta `uv run python <carpeta>/salida/figs.py <carpeta>/salida`.
- Inserta el SVG con
  `<figure class="fig"><img src="fig7-1.svg" style="width:10.5cm"><figcaption><b>Figura 7.1</b> pie</figcaption></figure>`.
  Ajusta el ancho al contenido: de 9 a 13 cm en los normales y hasta 16,4 cm en los grandes.
- **Solo blanco, negro y grises**, como el SOLID: nada de colores (ni `fill` ni `stroke` de
  color). Para distinguir zonas usa grises claros (`#ececec`, `#d0d0d0`) o líneas
  discontinuas. Si el original usa color con significado (por ejemplo, una línea roja), di
  en el pie cómo se representó.
- En los diagramas, los identificadores de código (clases, métodos) quedan en el idioma
  original. Las etiquetas en lenguaje natural van en el idioma de salida.
- Si añades algo que no estaba en el original, dilo en el pie:
  `<br><span style="color:#555">(…se han añadido en esta versión…)</span>`.

**Sin `mejorar_lectura`**, y en todo caso para las ilustraciones, fotos y capturas: conserva
la imagen original, `<figure class="fig"><img src="../figuras/fig-7.1.jpeg" style="width:11cm">…`,
o `<div class="ilustracion"><img src="../figuras/ilus-p064-1.jpeg" alt=""></div>` si es
decorativa.

Revisa los SVG complejos en el PDF (paso 7), no abriendo el SVG como texto.

### 5. Comentarios, contexto y resumen (solo lo que pida la tarea)
Todos van en recuadros `<div class="com"><span class="label">…</span>…</div>`, justo después
del pasaje que explican, y en el idioma de salida. Uno o dos por sección como máximo, y
ninguno que solo repita el texto.

**`comentarios`**: la parte de estudio, lo que un lector atento querría preguntar. Etiqueta
`Comentario · tema`. Tipos que funcionaron en el SOLID:
- **cómo leer la figura X**: qué significan las formas y las flechas;
- **la idea clave**: tabla «lo que no dice» / «lo que sí dice»;
- **por qué se llama…**: el origen de un término;
- **paso a paso**: código o razonamientos en una lista numerada;
- **comparación**: tabla de opciones con ventajas e inconvenientes;
- **qué significa**: identificadores, URLs o datos de ejemplo explicados;
- **ejemplo mínimo en código**, avisando de que no está en el documento (`.com.allow-break`
  si es largo).

**`contexto`**: antecedentes que el documento da por sabidos, o cómo se relaciona con otras
ideas. Sale de las **fuentes adicionales**: notas, enlaces y PDFs de apoyo. Si hace falta,
también de conocimiento general, dicho como tal. Etiqueta `Contexto · tema`, y al final del
recuadro, la fuente:
`<span class="fuente">Fuente: apuntes.pdf, p. 3 · https://…</span>`. No inventes citas: si
algo no está en las fuentes, no lo atribuyas a ellas.

**`resumen`**: al final, una página entera dentro de un `.com` con una tabla de repaso
(«Resumen final»), como la del SOLID.

Con `comentarios` y/o `contexto`, la portada lleva el recuadro «cómo leer este documento»,
que avisa de que los recuadros no forman parte del original. Si no hay ninguno de los dos,
quítalo.

### 6. Construir
`uv run atril construir <carpeta>`. Genera `salida/<parte>.pdf`,
`salida/<parte>-2-por-hoja.pdf` y `salida/revision/hoja-NN.png`, y marca la parte como
construida en `libro.json`.

### 7. Revisar y corregir
Mira cada `hoja-NN.png`. Busca:
- figuras partidas o demasiado grandes;
- páginas casi vacías antes de una figura;
- recuadros que desbordan;
- títulos huérfanos al pie de página;
- notas al pie que se comen la página;
- el índice sin números de página.

Para ver una página en detalle: `uv run atril ver <carpeta> 5,7-8`, que genera
`revision/p-005.png`. Corrige el HTML (o `figs.py`) y vuelve a construir hasta que esté
limpio. Avisa al usuario de lo que no pudiste resolver.

### 8. Actualizar `glosario.md`
Su ruta está en la cabecera (`glosario:`). Si hubo traducción, agrega los términos decididos;
si no, solo los términos o siglas que explicaste en comentarios o contexto (si hubo). No
borres lo anterior. Créalo si no existe, con este formato:

```markdown
## Términos

| Original | Traducción o explicación | Nota |
|---|---|---|
| stakeholder | parte interesada (*stakeholder*) | la primera vez, con el original entre paréntesis |
| SOLID | SOLID | nombre propio, no se traduce |

## Decisiones de estilo

- Identificadores de código en inglés, con `<code>`.
```

Termina con un resumen corto:
- las rutas de los dos PDFs y el número de páginas;
- qué se hizo según la tarea;
- las figuras redibujadas;
- las fuentes usadas para el contexto;
- los términos nuevos del glosario;
- lo que quedó pendiente.

## Estilo

**Estructura del HTML:**
- un `<section class="cap" id="cN">` por capítulo o sección grande;
- `<p class="num">7</p>` si el original numera (en una parte, número romano);
- `<h1 data-cap="7 · Título corto">`, con el título en el idioma de salida y, si se tradujo,
  `<span class="en">TÍTULO ORIGINAL EN MAYÚSCULAS</span>`. `data-cap` es el encabezado corto
  de página;
- secciones con `<h2>`;
- una entrada en el índice de la portada por cada capítulo o sección grande.

**Elementos del texto:**
- Notas al pie en línea, donde va la llamada: `<span class="fn">texto</span>`.
- Enunciados centrales: `<blockquote class="def">`. Citas: `<blockquote>`.
- Código: `<pre>` copiado tal cual (sus comentarios solo se traducen si el usuario lo pide).
  Código en línea con `<code>`.
- Tablas del documento con `<table class="cfg">`. Si el contenido es código, las celdas
  llevan `class="mono"`.

**Tipografía** del idioma de salida. En español:
- comillas latinas «», y para citas dentro de citas, “ ”;
- rayas, no guiones, para los incisos;
- «RR. HH.», «n.º», números con el formato del español.

## Traducción (solo si `traducir`)

**Español:** natural y neutro, tuteando al lector («si todavía no conoces…»). Usa la
sintaxis propia del español, no un calco del original.

**Términos:**
- La primera vez que aparece un término técnico que se suele dejar en inglés: «partes
  interesadas (<i>stakeholders</i>)». Después, solo en español.
- Patrones con nombre: «el patrón **Fachada** (<i>Facade</i>)».
- Los acrónimos se mantienen (SRP, OCP…), con su nombre desarrollado en español.
- Los nombres de clases, métodos y archivos se dejan en inglés. La primera vez puede ir la
  traducción entre paréntesis: «la clase `Employee` (empleado)».

**Errores de las traducciones automáticas que hay que evitar:**
- traducir nombres propios o acrónimos («principios SÓLIDOS»);
- falsos amigos («criterios» por *principles*, «eventualmente» por *eventually*,
  «implementación» por *deployment*);
- calcos de voz pasiva;
- dejar sin traducir frases enteras.
