---
name: libro
description: Traduce o mejora una parte de un libro a partir de un paquete de Atril (contexto.md + figuras/) y produce el PDF imprimible con diagramas redibujados y comentarios de estudio. Usar cuando el usuario escribe /libro <carpeta-de-la-parte> o pide procesar un paquete exportado con `atril exportar`.
argument-hint: <carpeta de la parte, la que tiene contexto.md>
---

# /libro: de un paquete de Atril al PDF final

Paquete: `$ARGUMENTS` (si viene vacío, pregunta la ruta o usa la última parte con
`uv run atril proyectos`). Trabaja desde `~/Projects/atril`: todos los comandos son
`uv run atril …`.

El caso modelo es `referencia/solid/solid.html` (Parte III de *Arquitectura Limpia*). Ante
cualquier duda de estilo, imita lo que hace ese archivo: busca el patrón con grep en lugar de
leerlo entero.

## Ahorro de plan

- `contexto.md` es lo único que se lee entero. Ya trae el texto limpio y fusionado.
- Los PDFs originales (rutas en la cabecera) se abren solo si un bloque se ve mal extraído:
  texto cortado, columnas mezcladas o una figura que falta. Lee únicamente esa página.
- La referencia es una ayuda: sirve para ver cómo se tradujo un término, pero **no se
  copia**. Suele ser una traducción automática con errores.
- Para revisar la maqueta, mira primero las hojas de miniaturas. Usa `atril ver` solo para
  las páginas con algún problema.

## Pasos

### 1. Leer el paquete
Lee `<carpeta>/contexto.md`. Fíjate en las instrucciones del usuario (mandan sobre esta skill),
el glosario acumulado, el índice de la parte y `idioma_destino`. Lista `<carpeta>/figuras/`.

### 2. Confirmar el plan con el usuario (una sola pregunta)
Presenta en pocas líneas:
- los capítulos o secciones y las páginas que ocupan;
- las figuras: cuáles se redibujan en SVG (diagramas) y cuáles se conservan como imagen
  (ilustraciones, fotos, capturas);
- los términos dudosos que aún no están en el glosario, con tu propuesta;
- dónde piensas poner comentarios y de qué tipo, más si habrá resumen final;
- cualquier cosa rara del paquete (páginas vacías, texto mal extraído).

Espera la respuesta antes de traducir.

### 3. Traducir capítulo por capítulo
Ejecuta `uv run atril iniciar <carpeta>`. Crea `salida/<parte>.html` desde la plantilla con
lo que se sabe sin IA y deja marcado con `COMPLETAR` lo que falta (portada, fuente).
Sustituye el capítulo de ejemplo por los reales y agrega cada capítulo al HTML apenas lo
termines, con Edit. No acumules todo para el final.

Reglas de traducción (ver «Estilo» más abajo):
- Fiel al **original**: frase por frase, sin resumir, sin omitir párrafos ni notas al pie y
  sin añadir nada fuera de los recuadros de comentario.
- Español natural y neutro, tuteando al lector: «si todavía no conoces…». Usa la sintaxis
  propia del español, no un calco del original.
- Sigue el glosario. Si tomas una decisión nueva, anótala para el paso 8.

### 4. Redibujar los diagramas
Por cada diagrama de `figuras/` (mira la imagen):
- Escribe su código en `salida/figs.py` con la librería `atril.svg`. Usa
  `referencia/solid/figs.py` como modelo de API y de medidas.
- Ejecuta `uv run python <carpeta>/salida/figs.py <carpeta>/salida`.
- Inserta el SVG con
  `<figure class="fig"><img src="fig7-1.svg" style="width:10.5cm"><figcaption><b>Figura 7.1</b> pie traducido</figcaption></figure>`.
  Ajusta el ancho al contenido: de 9 a 13 cm en los normales y hasta 16,4 cm en los grandes.
- **Solo blanco, negro y grises**, como el SOLID: nada de colores (ni `fill` ni `stroke` de
  color). Para distinguir zonas usa grises claros (`#ececec`, `#d0d0d0`) o líneas
  discontinuas. Si el original usa color con significado (por ejemplo, una línea roja), di
  en el pie cómo se representó.
- En los diagramas, los identificadores de código (clases, métodos) quedan en el idioma
  original. Se traducen las etiquetas en lenguaje natural: actores, almacenes, notas.
- Si añades algo que no estaba en el original, dilo en el pie:
  `<br><span style="color:#555">(…se han añadido en esta versión…)</span>`.
- Las ilustraciones decorativas (las de inicio de capítulo, por ejemplo) se conservan como
  imagen: `<div class="ilustracion"><img src="../figuras/ilus-p064-1.jpeg" alt=""></div>`.

Después de generar los SVG, revisa visualmente los más complejos en el PDF (paso 7). No
abras el SVG como texto para comprobarlo.

### 5. Escribir los comentarios
Recuadros `<div class="com"><span class="label">Comentario · tema</span>…</div>`, justo después
del pasaje que explican. Son la parte de estudio: lo que un lector atento querría preguntar.
Tipos que funcionaron en el SOLID:
- **cómo leer la figura X**: qué significan las formas y las flechas en esa figura concreta;
- **la idea clave**: tabla de dos columnas, «lo que no dice» y «lo que sí dice»;
- **por qué se llama…**: el origen de un término;
- **paso a paso**: código o razonamientos desglosados en una lista numerada;
- **comparación**: tabla de soluciones con sus ventajas e inconvenientes;
- **contexto**: una ley, una persona o un acrónimo que el libro da por sabido;
- **qué significa**: identificadores, URLs o datos de ejemplo traducidos al español;
- **ejemplo mínimo en código**, avisando de que no está en el libro (`.com.allow-break`
  si es largo).

Uno o dos por sección como máximo, y ninguno que solo repita el texto. Si cubre varios
capítulos, termina con un **Resumen final**: una página entera dentro de un `.com`, con una
tabla de repaso.

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
Su ruta está en la cabecera de `contexto.md` (`glosario:`). Créalo si no existe, con este
formato, y agrega las decisiones de esta parte sin borrar las anteriores:

```markdown
## Términos

| Original | Traducción | Nota |
|---|---|---|
| stakeholder | parte interesada (*stakeholder*) | la primera vez, con el original entre paréntesis |
| SOLID | SOLID | nombre propio, no se traduce |

## Decisiones de estilo

- Identificadores de código en inglés, con `<code>`.
```

Termina con un resumen corto: las rutas de los dos PDFs, el número de páginas, las figuras
redibujadas, los términos nuevos del glosario y lo que quedó pendiente.

## Estilo (del caso SOLID)

**Estructura del HTML:**
- un `<section class="cap" id="cN">` por capítulo;
- `<p class="num">7</p>` (en una parte, número romano);
- `<h1 data-cap="7 · SRP: principio de responsabilidad única">`, con el título traducido y
  `<span class="en">TÍTULO ORIGINAL EN MAYÚSCULAS</span>`. `data-cap` es el encabezado corto
  de página;
- secciones con `<h2>`;
- una entrada en el índice de la portada por cada capítulo.

**Elementos del texto:**
- Notas al pie en línea, donde va la llamada: `<span class="fn">texto</span>`.
- Enunciados centrales: `<blockquote class="def">`. Citas: `<blockquote>`.
- Código del libro: `<pre>` sin traducir (solo se traducen sus comentarios, y solo si el
  usuario lo pide). Código en línea con `<code>`.
- Tablas del libro con `<table class="cfg">`. Si el contenido es código, las celdas llevan
  `class="mono"`.

**Términos:**
- La primera vez que aparece un término técnico que se suele dejar en inglés: «partes
  interesadas (<i>stakeholders</i>)», «fusiones (<i>merges</i>)». Después, solo en español.
- Patrones con nombre: «el patrón **Fachada** (<i>Facade</i>)».
- Los acrónimos se mantienen (SRP, OCP…), con su nombre desarrollado en español.
- Los nombres de clases, métodos y archivos se dejan en inglés. La primera vez puede ir la
  traducción entre paréntesis: «la clase `Employee` (empleado)».

**Tipografía:**
- Comillas latinas «», y para citas dentro de citas, “ ”.
- Rayas, no guiones, para los incisos.
- «RR. HH.», «n.º», números con el formato del español.

**Errores de la referencia que hay que evitar:**
- traducir nombres propios o acrónimos («principios SÓLIDOS»);
- falsos amigos («criterios» por *principles*, «eventualmente» por *eventually*);
- calcos de voz pasiva;
- dejar sin traducir frases enteras.
