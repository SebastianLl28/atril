# Atril

Arma paquetes de contexto para traducir y mejorar libros por partes con Claude Code, sin usar
la API de pago. El plan completo está en [PLAN.md](PLAN.md).

## Uso

```fish
# 1. Crear el proyecto del libro: original + referencia opcional; calcula el mapa de páginas
uv run atril nuevo arquitectura-limpia --titulo "Arquitectura Limpia" \
    --original "~/Documents/books/Arquitectura Limpia - ingles.pdf" \
    --referencia "~/Documents/books/Arquitectura Limpia - Español.pdf"

# 2. Ubicar la parte: índice del original y consulta o corrección del mapa
uv run atril indice arquitectura-limpia
uv run atril mapa arquitectura-limpia --referencia 77-108      # → páginas del original
uv run atril mapa arquitectura-limpia --ancla 77=62            # corregir a mano

# 3. Exportar el paquete: basta con un rango, el otro sale del mapa
uv run atril exportar arquitectura-limpia parte-03-solid --original 62-86 \
    --instrucciones notas.txt --titulo-parte "III · Principios de diseño"
```

Después, en Claude Code abierto en este repo: `/libro <carpeta de la parte>`. La skill traduce,
redibuja los diagramas y comenta; para la salida usa estos comandos, que también se pueden
correr a mano:

```fish
uv run atril iniciar   ~/Documents/books/proyectos/arquitectura-limpia/parte-03-solid  # HTML desde la plantilla
uv run atril construir ~/Documents/books/proyectos/arquitectura-limpia/parte-03-solid  # PDF, 2 por hoja, miniaturas
uv run atril ver       ~/Documents/books/proyectos/arquitectura-limpia/parte-03-solid 5,7-8
```

Los proyectos se guardan en `~/Documents/books/proyectos/<libro>/`. Para cambiar la carpeta,
usa la variable `ATRIL_PROYECTOS`.

## Estructura

- `src/atril/`: núcleo (`pdf`, `limpieza`, `mapa`, `paquete`, `proyecto`, `cli`) y salida
  (`construir`, `svg`, `plantilla/`)
- `.claude/skills/libro/`: la skill `/libro`
- `referencia/solid/`: el caso SOLID hecho a mano (HTML, CSS de impresión, SVG); es el modelo
  de estilo de la skill y la prueba de regresión de la plantilla
- `tests/`: pruebas con la Parte III del libro real y con el caso SOLID

```fish
uv run pytest
```
