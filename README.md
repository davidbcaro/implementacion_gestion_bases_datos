# Implementación y gestión de bases de datos — SENA (228130)

Este sitio reúne el material educativo del programa **Implementación y gestión de bases de
datos** para consultarlo de forma ordenada por fase y actividad de proyecto.

## ¿Qué encontrarás?

- **4 fases del proyecto:** Análisis, Planeación, Ejecución y Evaluación.
- **7 actividades de proyecto**, repartidas entre las fases.
- **12 guías de aprendizaje** con las orientaciones y actividades de formación.
- **Materiales de formación** sobre modelado de datos, SQL, NoSQL, bodegas de datos,
  seguridad de bases de datos, servidores y otros temas del programa.
- **Objetos Virtuales de Aprendizaje (OVA)** interactivos para complementar el estudio.
- **Documentación de apoyo:** información general del programa, actividades iniciales,
  cronograma y etapa productiva.

## ¿Cómo usarlo?

Desde la portada puedes buscar una guía, un OVA o un documento en todo el programa, o
entrar directamente a la fase que estás cursando. En cada fase encontrarás sus guías y
materiales organizados por actividad de proyecto.

Los OVA se abren en una pestaña nueva para que puedas estudiar sus contenidos
interactivos. Las actividades, foros y entrega de evidencias continúan realizándose en
la plataforma oficial de formación.

## Proyecto formativo

Análisis y construcción de bases de datos orientado a todo tipo de organizaciones.

## Cómo se construye

Requiere Python 3 (y `pdftotext` para leer los metadatos de las guías; sin él, el sitio
se genera igual pero sin la descripción de cada actividad de proyecto).

```bash
python herramientas/extraer_ovas.py && python herramientas/generar_sitio.py
```

- **`extraer_ovas.py`** descomprime cada `material.zip` en una carpeta `ova/` al lado,
  normaliza el envoltorio que traen algunos paquetes y omite la copia interna que cada
  OVA lleva de sí mismo. Es idempotente: salta lo ya extraído salvo que se le pase
  `--forzar`.
- **`generar_sitio.py`** recorre las carpetas, lee el título real de cada OVA desde su
  `index.html`, extrae la actividad de proyecto de la primera página de cada guía y
  escribe las páginas HTML.

El color de cada fase se cambia en `FASES`, dentro de `herramientas/generar_sitio.py`.
Todo lo que se pinta encima —titulares, cifras, numeral y estado apagado— se recalcula a
partir de ese color, y el generador avisa si alguno deja el texto por debajo del contraste
mínimo legible.

## Ver el sitio en local

```bash
python -m http.server 8777
```

Y abrir <http://127.0.0.1:8777/>.
