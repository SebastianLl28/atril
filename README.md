# Atril

Prepara documentos para leerlos y estudiarlos mejor con Claude Code, sin usar la API de pago:
libros, informes, apuntes. Eliges páginas de un PDF con texto y decides qué hacer con ellas:
- transcribir con una maquetación limpia y los diagramas redibujados;
- traducir;
- agregar comentarios de estudio o contexto a partir de otras fuentes (notas, enlaces, otros
  PDFs);
- cualquier combinación de lo anterior.

Atril arma un paquete con el texto ya limpio y la skill `/libro` produce el PDF imprimible.
No acepta PDFs que son solo imágenes (escaneos sin capa de texto). El plan completo está en
[PLAN.md](PLAN.md).

## Uso

La forma más fácil es la app visual: `uv run atril app` abre el navegador.
1. Se crea el proyecto con el PDF del documento y, si se quiere, la misma obra en otro idioma
   para verlas lado a lado.
2. Se eligen las páginas: un capítulo desde el índice o, si el PDF no trae índice, con clic y
   mayús+clic.
3. En «Qué hacer con estas páginas» se elige la tarea y se suman fuentes adicionales.
4. Al exportar, la app muestra el comando `/libro …` listo para copiar.

Lo mismo se puede hacer por línea de comandos:

```fish
# 1. Crear el proyecto: el documento y, opcional, otra versión en otro idioma (calcula el mapa)
uv run atril nuevo arquitectura-limpia --titulo "Arquitectura Limpia" \
    --original "~/Documents/books/Arquitectura Limpia - ingles.pdf" \
    --referencia "~/Documents/books/Arquitectura Limpia - Español.pdf"

# 2. Ubicar la parte: índice del original y consulta o corrección del mapa
uv run atril indice arquitectura-limpia
uv run atril mapa arquitectura-limpia --referencia 77-108      # → páginas del original
uv run atril mapa arquitectura-limpia --ancla 77=62            # corregir a mano

# 3. Exportar la parte con su tarea (por defecto: mismo idioma, mejorar la lectura)
uv run atril exportar arquitectura-limpia parte-03-solid --original 62-86 \
    --traducir es --comentarios --contexto \
    --notas apuntes.md --enlace https://es.wikipedia.org/wiki/SOLID --pdf "otro.pdf:3-8" \
    --titulo-parte "III · Principios de diseño"
```

Después, en Claude Code abierto en este repo: `/libro <carpeta de la parte>`. La skill hace lo
que diga la tarea (transcribir o traducir, redibujar, comentar, dar contexto); para la salida usa estos comandos, que también se pueden
correr a mano:

```fish
uv run atril iniciar   ~/Documents/books/proyectos/arquitectura-limpia/parte-03-solid  # HTML desde la plantilla
uv run atril construir ~/Documents/books/proyectos/arquitectura-limpia/parte-03-solid  # PDF, 2 por hoja, miniaturas
uv run atril ver       ~/Documents/books/proyectos/arquitectura-limpia/parte-03-solid 5,7-8
```

Otros comandos:

```fish
uv run atril indice arquitectura-limpia --referencia        # índice detectado si el PDF no trae
uv run atril imprimir <carpeta-de-la-parte> --2-por-hoja --simular   # quita --simular para imprimir
```

Los proyectos se guardan en `~/Documents/books/proyectos/<libro>/`. Para cambiar la carpeta,
usa la variable `ATRIL_PROYECTOS`.

## Estructura

- `src/atril/`: núcleo (`pdf`, `limpieza`, `mapa`, `paquete`, `proyecto`, `cli`) y salida
  (`construir`, `svg`, `plantilla/`) la app (`app`, `miniaturas`, `web/`) e `imprimir`
- `.claude/skills/libro/`: la skill `/libro`
- `referencia/solid/`: el caso SOLID hecho a mano (HTML, CSS de impresión, SVG); es el modelo
  de estilo de la skill y la prueba de regresión de la plantilla
- `tests/`: pruebas con la Parte III del libro real y con el caso SOLID

```fish
uv run pytest
```
