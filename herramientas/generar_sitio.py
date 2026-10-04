# -*- coding: utf-8 -*-
"""Genera el sitio web estatico del programa a partir de la estructura de carpetas.

Recorre fases > actividades de proyecto > guias / materiales de formacion, lee el
titulo real de cada OVA desde su index.html y produce:

    index.html                 portada con las fases
    fase-1.html ... fase-4.html
    informacion-general.html   secciones 00 y 99
    assets/estilo.css, assets/sitio.js
    .nojekyll                  evita que GitHub Pages procese el sitio con Jekyll

No modifica ningun material: solo enlaza a los archivos existentes.

Uso:  python herramientas/generar_sitio.py
"""
import hashlib
import html
import json
import os
import re
import subprocess
import zipfile
import unicodedata
from urllib.parse import quote

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPA_OVAS = os.path.join(RAIZ, 'herramientas', 'ovas.json')
TITULOS_JSON = os.path.join(RAIZ, 'herramientas', 'titulos.json')

PROGRAMA = {
    'nombre': 'Implementación y gestión de bases de datos',
    'codigo': '228130',
    'nivel': 'Tecnólogo',
    'horas': '3984',
    'duracion': '27 meses',
    'modalidad': 'Virtual',
    'proyecto': ('Análisis y construcción de bases de datos orientado a todo tipo '
                 'de organizaciones.'),
}

# Las carpetas del repositorio no llevan tildes; aqui se recupera el nombre correcto.
# ===========================================================================
#  COLOR DE CADA FASE
#  Cambia aqui el `color` de una fase y cambia su panel en la portada y la
#  cabecera de su pagina. Todo lo que se pinta encima —titulares, cifras,
#  numeral, estado apagado— se recalcula solo a partir de ese valor, asi que
#  puedes poner el color que quieras: el generador avisa si alguno deja el
#  texto por debajo del contraste minimo.
# ===========================================================================
FASES = {
    'Fase 1 - Analisis': {'nombre': 'Análisis', 'numero': 1, 'color': '#dcefd2'},
    'Fase 2 - Planeacion': {'nombre': 'Planeación', 'numero': 2, 'color': '#cfe8e0'},
    'Fase 3 - Ejecucion': {'nombre': 'Ejecución', 'numero': 3, 'color': '#d4e5f2'},
    'Fase 4 - Evaluacion': {'nombre': 'Evaluación', 'numero': 4, 'color': '#e0e2f0'},
}

# Tintas base sobre campo claro y sobre campo oscuro.
TINTA_OSCURA = '#0a1710'
TINTA_CLARA = '#ffffff'
PAPEL = '#f2f5f1'
SECCIONES_EXTRA = [
    ('00 - Informacion general', 'Información general',
     'Documentos institucionales del programa, material de apoyo y guías para el aprendiz.'),
    ('00 - Actividades iniciales', 'Actividades iniciales',
     'Trámites y formatos que se diligencian al comenzar la formación.'),
    ('00 - Cronograma', 'Cronograma',
     'Distribución del programa en el tiempo.'),
    ('99 - Etapa productiva', 'Etapa productiva',
     'Orientaciones para la etapa práctica en la empresa.'),
]

# Correcciones puntuales de titulos: el primero viene con una errata en el propio
# OVA y el segundo no tiene OVA del que leer el titulo.
TITULOS_CORREGIDOS = {
    'Gestión de dispositivos de reds': 'Gestión de dispositivos de red',
    'Validacion de estandares y normatividad vigente': 'Validación de estándares y normatividad vigente',
}

# Los nombres de archivo del repositorio no llevan tildes; aqui se restituyen.
NOMBRES_CORREGIDOS = {
    'Actualizacion datos aprendiz': 'Actualización de datos del aprendiz',
    'Cronogramas': 'Cronogramas (formatos)',
    'Diseno curricular': 'Diseño curricular',
    'Enrutamiento estatico y dinamico': 'Enrutamiento estático y dinámico',
    'Enrutamiento inter VLAN': 'Enrutamiento inter-VLAN',
    'Guia buen uso foros': 'Guía de buen uso de los foros',
    'Informacion del programa': 'Información del programa',
    'Instrumentos evaluacion': 'Instrumentos de evaluación',
    'Introduccion a las computadoras personales': 'Introducción a las computadoras personales',
    'Manual LMS Aprendiz': 'Manual del LMS para el aprendiz',
    'Manual LMS Instructor': 'Manual del LMS para el instructor',
    'Parqueo y Conferencias': 'Parqueo y conferencias',
    'Planeacion Pedagogica': 'Planeación pedagógica',
    'Presentacion charlas Etapa Productiva aprendices': 'Charlas de etapa productiva para aprendices',
    'Proyecto Formativo': 'Proyecto formativo',
    'Que son los canales wifi': '¿Qué son los canales wifi?',
    'Todo sobre la telefonia IP': 'Todo sobre la telefonía IP',
    'VLAN Redes Locales Virtuales': 'VLAN: redes locales virtuales',
    'Documentos de interes para el aprendiz': 'Documentos de interés para el aprendiz',
    'Comunicacion oral y escrita': 'Comunicación oral y escrita',
}


TIPOS = {
    '.pdf': ('PDF', 'documento'),
    '.zip': ('ZIP', 'comprimido'),
    '.pptx': ('PPTX', 'presentación'),
    '.ppt': ('PPT', 'presentación'),
    '.docx': ('DOCX', 'documento'),
    '.doc': ('DOC', 'documento'),
    '.xlsx': ('XLSX', 'hoja de cálculo'),
    '.xls': ('XLS', 'hoja de cálculo'),
}


# --------------------------------------------------------------------------- utilidades

def _canal(v):
    v = v / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminancia(color):
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _canal(r) + 0.7152 * _canal(g) + 0.0722 * _canal(b)


def contraste(a, b):
    la, lb = luminancia(a), luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def mezclar(a, b, peso):
    """El color `a` al `peso` indicado sobre `b`."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#{:02x}{:02x}{:02x}'.format(
        *(round(x * peso + y * (1 - peso)) for x, y in zip(ca, cb)))


def paleta_fase(color, nombre=''):
    """Deriva del color de la fase todo lo que se pinta encima.

    Devuelve el campo, su tinta principal y atenuada, el numeral y la versión
    apagada del campo, comprobando que ninguna pareja baje del mínimo legible.
    """
    claro = luminancia(color) > 0.3
    tinta = TINTA_OSCURA if claro else TINTA_CLARA
    paleta = {
        'campo': color,
        'tinta': tinta,
        'suave': mezclar(tinta, color, 0.72),
        # El campo identifica la fase; el numeral sigue siendo la marca SENA.
        'numeral': '#2e7d00' if claro else '#5fd424',
        'apagado': mezclar(color, PAPEL, 0.32) if claro else mezclar(color, '#050906', 0.4),
    }
    for clave, minimo in (('tinta', 4.5), ('suave', 4.5), ('numeral', 3.0)):
        real = contraste(paleta[clave], color)
        if real < minimo:
            print('  AVISO  {}: «{}» sobre {} da {:.2f}:1, por debajo de {}:1'.format(
                nombre or color, clave, color, real, minimo))
    return paleta


def vars_fase(paleta):
    """Las variables CSS que llevan el color de la fase al marcado."""
    return ('--campo:{campo};--campo-tinta:{tinta};--campo-suave:{suave};'
            '--campo-numeral:{numeral};--campo-apagado:{apagado}').format(**paleta)


def plural(n, singular, prural=None):
    return '{} {}'.format(n, singular if n == 1 else (prural or singular + 's'))


def e(t):
    return html.escape(str(t), quote=True)


def url(ruta_rel):
    return quote(ruta_rel.replace(os.sep, '/'))


def firma(ruta):
    h = hashlib.md5()
    with open(ruta, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def titulo_ova(carpeta_ova):
    """Lee el <title> real del OVA; si no lo encuentra, devuelve None."""
    idx = os.path.join(RAIZ, carpeta_ova.replace('/', os.sep), 'index.html')
    try:
        with open(idx, 'r', encoding='utf-8', errors='replace') as f:
            cabeza = f.read(4000)
    except OSError:
        return None
    m = re.search(r'<title>(.*?)</title>', cabeza, re.S | re.I)
    if not m:
        return None
    t = re.sub(r'\s+', ' ', m.group(1)).strip()
    return t or None


def limpiar_nombre(nombre):
    """'01 - Hardware y software...' -> ('01', 'Hardware y software...')"""
    m = re.match(r'^(\d+)\s*-\s*(.+)$', nombre)
    return (m.group(1), m.group(2).strip()) if m else ('', nombre)


def describir_zip(ruta):
    """Cuenta documentos y anexos dentro de un ZIP de contenido."""
    try:
        with zipfile.ZipFile(ruta) as z:
            nombres = [n for n in z.namelist() if not n.endswith('/')]
    except (zipfile.BadZipFile, OSError):
        return None
    anexos = sum(1 for n in nombres if 'anexo' in n.lower())
    return len(nombres), anexos


def titulo_archivo(nombre, ruta, contexto):
    """Etiqueta legible para el boton de descarga segun donde aparece el archivo."""
    base = os.path.splitext(nombre)[0]
    limpio = re.sub(r'[_-]+', ' ', base).strip()
    ext = os.path.splitext(nombre)[1].lower()

    if contexto == 'guia':
        return 'Guía en PDF'
    if contexto == 'anexo':
        corto = re.sub(r'^Anexo\s+', '', limpio) or limpio
        return NOMBRES_CORREGIDOS.get(corto, corto)
    if contexto == 'material':
        if ext == '.pdf':
            return 'Contenido en PDF'
        if ext == '.zip':
            info = describir_zip(ruta)
            if info:
                total, anexos = info
                if anexos:
                    return 'Contenido + {} (ZIP)'.format(plural(anexos, 'anexo'))
                if total > 1:
                    return '{} (ZIP)'.format(plural(total, 'documento'))
            return 'Contenido (ZIP)'
    return NOMBRES_CORREGIDOS.get(limpio, limpio)


def archivos_de(carpeta, saltar=(), contexto='documento', principal=None):
    """Archivos descargables de una carpeta, sin duplicados por contenido."""
    if not os.path.isdir(carpeta):
        return []
    vistos = {}
    salida = []
    for nombre in sorted(os.listdir(carpeta)):
        ruta = os.path.join(carpeta, nombre)
        if not os.path.isfile(ruta) or nombre in saltar or nombre.startswith('.'):
            continue
        ext = os.path.splitext(nombre)[1].lower()
        if ext not in TIPOS:
            continue
        f = firma(ruta)
        if f in vistos:
            continue  # p. ej. CF1.zip y 228183_CF01_DU.zip son el mismo archivo
        vistos[f] = nombre
        etiqueta, clase = TIPOS[ext]
        es_principal = bool(principal) and nombre.lower().startswith(principal)
        ctx = contexto if contexto != 'guia' else ('guia' if es_principal else 'anexo')
        salida.append({
            'nombre': nombre,
            'titulo': titulo_archivo(nombre, ruta, ctx),
            'ruta': os.path.relpath(ruta, RAIZ),
            'etiqueta': etiqueta,
            'clase': clase,
        })

    # Una carpeta puede traer varios documentos del mismo tipo. Si la etiqueta
    # generica se repite, los botones quedan indistinguibles: en ese caso cada
    # uno pasa a llevar su propio nombre de archivo.
    repetidos = {t for t in (a['titulo'] for a in salida)
                 if [a['titulo'] for a in salida].count(t) > 1}
    for a in salida:
        if a['titulo'] in repetidos:
            limpio = re.sub(r'[_-]+', ' ', os.path.splitext(a['nombre'])[0]).strip()
            a['titulo'] = NOMBRES_CORREGIDOS.get(limpio, limpio)
    return salida


def metadatos_guia(pdf):
    """Extrae fase y actividad de proyecto de la primera pagina de la guia."""
    if not pdf:
        return {}
    try:
        crudo = subprocess.run(['pdftotext', '-enc', 'UTF-8', '-f', '1', '-l', '1', pdf, '-'],
                               capture_output=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    t = crudo.decode('utf-8', 'replace')
    # pdftotext deja las vinetas de Word como caracteres de uso privado (Wingdings)
    t = re.sub('[\ue000-\uf8ff]', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    m = re.search(r'Actividad de proyecto:\s*(.*?)\s*(?:Competencia|Resultados)', t)
    # Las guias traen vinetas de varios tipos segun como se exporto el PDF:
    # las de uso privado (Wingdings) ya se fueron arriba; estas son Unicode.
    ap = re.sub(r'[\s•·●○▪■∙º]+$', '', m.group(1)).strip() if m else ''
    return {'actividad': ap}


# --------------------------------------------------------------------------- recoleccion

def recolectar():
    mapa_ovas = {}
    if os.path.exists(MAPA_OVAS):
        with open(MAPA_OVAS, encoding='utf-8') as f:
            mapa_ovas = json.load(f)
    # Titulos de todos los paquetes, incluidos los que no se publican: sin esto
    # un material sin OVA caeria al nombre de su carpeta, que va sin tildes.
    titulos_paquete = {}
    if os.path.exists(TITULOS_JSON):
        with open(TITULOS_JSON, encoding='utf-8') as f:
            titulos_paquete = json.load(f)

    fases = []
    for carpeta, cfg in sorted(FASES.items(), key=lambda kv: kv[1]['numero']):
        nombre, numero = cfg['nombre'], cfg['numero']
        base = os.path.join(RAIZ, carpeta)
        if not os.path.isdir(base):
            continue
        fase = {'carpeta': carpeta, 'nombre': nombre, 'numero': numero,
                'pagina': 'fase-{}.html'.format(numero),
                'paleta': paleta_fase(cfg['color'], 'Fase {}'.format(numero)),
                'actividades': []}
        for act in sorted(os.listdir(base)):
            ruta_act = os.path.join(base, act)
            if not os.path.isdir(ruta_act):
                continue
            actividad = {'nombre': act, 'descripcion': '', 'guias': [], 'materiales': []}

            # Guias de aprendizaje
            guias = [d for d in os.listdir(ruta_act)
                     if d.lower().startswith('guia') and os.path.isdir(os.path.join(ruta_act, d))]
            for g in sorted(guias, key=lambda s: int(re.search(r'(\d+)', s).group(1))):
                ruta_g = os.path.join(ruta_act, g)
                todos = archivos_de(ruta_g, contexto='guia', principal='guia')
                principal = next((a for a in todos if a['nombre'].lower().startswith('guia')), None)
                anexos = [a for a in todos if a is not principal]
                numero_g = int(re.search(r'(\d+)', g).group(1))
                meta = metadatos_guia(os.path.join(RAIZ, principal['ruta']) if principal else None)
                if meta.get('actividad') and not actividad['descripcion']:
                    actividad['descripcion'] = meta['actividad']
                actividad['guias'].append({
                    'numero': numero_g, 'nombre': g,
                    'pdf': principal, 'anexos': anexos,
                })

            # Materiales de formacion
            ruta_mf = os.path.join(ruta_act, 'Material de formacion')
            if os.path.isdir(ruta_mf):
                for tema in sorted(os.listdir(ruta_mf)):
                    ruta_t = os.path.join(ruta_mf, tema)
                    if not os.path.isdir(ruta_t):
                        continue
                    orden, limpio = limpiar_nombre(tema)
                    rel_t = os.path.relpath(ruta_t, RAIZ).replace(os.sep, '/')
                    ova = mapa_ovas.get(rel_t)
                    titulo = ((titulo_ova(ova) if ova else None)
                              or titulos_paquete.get(rel_t) or limpio)
                    titulo = TITULOS_CORREGIDOS.get(titulo, titulo)
                    # 'Comunicacion oral y escrita. Argumentacion' -> serie + titulo corto
                    serie = ''
                    # La serie se muestra cuando el titulo del OVA es solo la
                    # segunda parte del nombre de la carpeta («Comunicacion oral
                    # y escrita. Relacionando» -> serie + «Relacionando»).
                    if '. ' in limpio and normalizar(titulo) != normalizar(limpio):
                        serie = limpio.split('. ')[0]
                        serie = NOMBRES_CORREGIDOS.get(serie, serie)
                    compartido = bool(ova) and not ova.startswith(rel_t)
                    origen = ''
                    if compartido:
                        raiz_origen = ova.split('/')[0]
                        origen = ('Fase {numero} · {nombre}'.format(**FASES[raiz_origen])
                                  if raiz_origen in FASES else '')
                    actividad['materiales'].append({
                        'orden': orden,
                        'titulo': titulo,
                        'serie': serie,
                        'carpeta': limpio,
                        'ova': (ova + '/index.html') if ova else None,
                        'compartido': compartido,
                        'origen': origen,
                        'descargas': archivos_de(ruta_t, saltar=('material.zip',),
                                                 contexto='material'),
                    })
            fase['actividades'].append(actividad)
        fases.append(fase)

    secciones = []
    for carpeta, nombre, descripcion in SECCIONES_EXTRA:
        base = os.path.join(RAIZ, carpeta)
        if not os.path.isdir(base):
            continue
        grupos = [{'nombre': None, 'archivos': archivos_de(base)}]
        for sub in sorted(os.listdir(base)):
            ruta_s = os.path.join(base, sub)
            if os.path.isdir(ruta_s):
                grupos.append({'nombre': sub, 'archivos': archivos_de(ruta_s)})
        secciones.append({'carpeta': carpeta, 'nombre': nombre,
                          'descripcion': descripcion,
                          'grupos': [g for g in grupos if g['archivos']]})
    return fases, secciones


# --------------------------------------------------------------------------- señalética
# El sitio se compone como el directorio de una estación: franja de identidad
# fija, buscador como control único, y bandas de zona a sangre.

LUPA = ('<svg class="lupa" width="22" height="22" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true">'
        '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.8-3.8"/></svg>')

FLECHA = ('<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
          'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
          '<path d="M5 12h13M12 5l7 7-7 7"/></svg>')

SALIR = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
         'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
         '<path d="M7 17 17 7M9 7h8v8"/></svg>')

BAJAR = ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
         'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
         '<path d="M12 4v11m0 0 4.5-4.5M12 15l-4.5-4.5M5 19h14"/></svg>')


def pagina(titulo, cuerpo, descripcion='', fase='', reposo=''):
    return '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{descripcion}">
<link rel="preload" href="assets/fonts/archivo-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="assets/estilo.css">
</head>
<body{fase}>
{franja}
{consulta}
{recuento}
{cuerpo}
<footer class="pie"><div class="contenedor">
  <span><b>SENA</b> · Servicio Nacional de Aprendizaje</span>
  <span>{programa} · Código {codigo} · {nivel}</span>
  <span class="pie-autor">David Bohorquez · <a class="pie-github" href="https://github.com/davidbcaro" target="_blank" rel="noopener noreferrer" aria-label="GitHub de David Bohorquez" title="GitHub de David Bohorquez"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.084-.729.084-.729 1.205.085 1.84 1.237 1.84 1.237 1.07 1.834 2.809 1.305 3.495.998.108-.776.418-1.305.762-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.046.138 3.006.404 2.292-1.552 3.297-1.23 3.297-1.23.647 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.43.372.81 1.102.81 2.222 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.63-5.373-12-12-12"/></svg></a></span>
</div></footer>
<script src="assets/indice.js"></script>
<script src="assets/sitio.js"></script>
</body>
</html>
'''.format(
        titulo=e(titulo), descripcion=e(descripcion), cuerpo=cuerpo,
        fase=' data-fase="{}"'.format(fase) if fase else '',
        franja=franja(), consulta=consulta(), recuento=barra_recuento(reposo),
        programa=e(PROGRAMA['nombre']), codigo=e(PROGRAMA['codigo']),
        nivel=e(PROGRAMA['nivel']))


def franja():
    return ('<header class="franja"><div class="contenedor">'
            '<a class="franja-marca" href="index.html" data-lleva-consulta="index.html">'
            '<span class="sigla">SENA</span><span class="prog">{prog}</span></a>'
            '<span class="franja-codigo">{codigo} · {nivel}</span>'
            '</div></header>').format(
        prog=e(PROGRAMA['nombre']), codigo=e(PROGRAMA['codigo']),
        nivel=e(PROGRAMA['nivel'].upper()))


def consulta():
    return ('<div class="consulta"><div class="contenedor"><div class="consulta-caja">'
            '{lupa}'
            '<label class="solo-lectores" for="buscador">Buscar en todo el programa</label>'
            '<input id="buscador" type="search" autocomplete="off" spellcheck="false" '
            'placeholder="Buscar una guía, un OVA o un documento…">'
            '<button id="limpiar" class="consulta-limpiar" type="button">Limpiar</button>'
            '</div></div></div>').format(lupa=LUPA)


def barra_recuento(reposo):
    return ('<div class="recuento"><div class="contenedor">'
            '<span id="recuento" data-reposo="{r}" aria-live="polite">{r}</span>'
            '</div></div>').format(r=e(reposo))


def chip_descarga(archivo, texto=None):
    """El boton de un documento.

    Un PDF se abre en una pestaña nueva: el navegador lo muestra en su propio
    visor y el aprendiz puede leerlo sin guardar nada. Los demas formatos
    (ZIP, PPTX, DOCX, XLSX) no se pueden mostrar en el navegador, asi que esos
    si se descargan.
    """
    es_pdf = archivo['nombre'].lower().endswith('.pdf')
    if es_pdf:
        modo = ' target="_blank" rel="noopener"'
        titulo_html = 'Abrir {} en una pestaña nueva'.format(archivo['nombre'])
        icono = SALIR
    else:
        modo = ' download'
        titulo_html = 'Descargar {}'.format(archivo['nombre'])
        icono = BAJAR
    return ('<a class="boton boton-archivo" href="{href}"{modo} title="{titulo_html}">'
            '<span class="tipo">{tipo}</span><span>{titulo}</span>{icono}</a>').format(
        href=url(archivo['ruta']), modo=modo, titulo_html=e(titulo_html),
        tipo=e(archivo['etiqueta']), titulo=e(texto or archivo['titulo'][:46]),
        icono=icono)


def fila_guia(guia):
    buscable = 'Guía de aprendizaje {} {}'.format(
        guia['numero'], ' '.join(a['titulo'] for a in guia['anexos']))
    p = ['<article class="fila" data-buscable="{}">'.format(e(buscable))]
    p.append('<span class="fila-orden">{:02d}</span><div class="fila-cuerpo">'.format(guia['numero']))
    p.append('<h3 class="fila-titulo">Guía de aprendizaje {}</h3>'.format(guia['numero']))
    if guia['anexos']:
        p.append('<span class="fila-serie">{}</span>'.format(
            e(plural(len(guia['anexos']), 'anexo') + ' de apoyo')))
    p.append('<div class="acciones">')
    if guia['pdf']:
        p.append(chip_descarga(guia['pdf']))
    for a in guia['anexos']:
        p.append(chip_descarga(a))
    p.append('</div></div></article>')
    return ''.join(p)


def fila_material(material):
    buscable = ' '.join([material['titulo'], material['serie'], material['carpeta']] +
                        [d['titulo'] for d in material['descargas']])
    p = ['<article class="fila" data-buscable="{}">'.format(e(buscable))]
    p.append('<span class="fila-orden">{}</span><div class="fila-cuerpo">'.format(
        e(material['orden'] or '·')))
    titulo = ('{}: {}'.format(material['serie'], material['titulo'])
              if material['serie'] else material['titulo'])
    p.append('<h3 class="fila-titulo">{}</h3>'.format(e(titulo)))

    # Lo ausente y lo compartido se dibujan, no se omiten.
    if not material['ova']:
        if material['descargas']:
            p.append('<span class="marca marca-sin-ova">Sin OVA · solo descarga</span>')
        else:
            # Ni OVA publicado ni documento suelto: se dice dónde está, en vez
            # de dejar una fila sin nada que abrir.
            p.append('<span class="marca marca-sin-ova">'
                     'Disponible en la plataforma oficial</span>')
    elif material['compartido'] and material['origen']:
        p.append('<span class="marca marca-compartido">Mismo OVA de {}</span>'.format(
            e(material['origen'])))

    p.append('<div class="acciones">')
    if material['ova']:
        p.append('<a class="boton boton-ova" href="{}" target="_blank" rel="noopener">'
                 'Abrir OVA{}</a>'.format(url(material['ova']), SALIR))
    for d in material['descargas']:
        p.append(chip_descarga(d))
    p.append('</div></div></article>')
    return ''.join(p)


def rotulo(titulo, cuenta=''):
    return ('<div class="rotulo"><h2>{}</h2>{}</div>').format(
        e(titulo),
        '<span class="cuenta">{}</span>'.format(e(cuenta)) if cuenta else '')


# --------------------------------------------------------------------------- índice

def normalizar(texto):
    t = unicodedata.normalize('NFD', texto.lower())
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn')


def ancla(texto):
    return re.sub(r'[^a-z0-9]+', '-', normalizar(texto)).strip('-')


def construir_indice(fases, secciones):
    """Índice plano de todo el programa; se sirve una vez y se cachea."""
    idx = []
    for fase in fases:
        donde = 'Fase {} · {}'.format(fase['numero'], fase['nombre'])
        n = fase['numero']
        for act in fase['actividades']:
            for g in act['guias']:
                if g['pdf']:
                    idx.append({'t': 'Guía de aprendizaje {}'.format(g['numero']),
                                'd': donde, 'k': 'PDF', 'u': url(g['pdf']['ruta']), 'f': n})
                for a in g['anexos']:
                    idx.append({'t': a['titulo'], 'd': donde + ' · Guía {}'.format(g['numero']),
                                'k': a['etiqueta'], 'u': url(a['ruta']), 'f': n})
            for m in act['materiales']:
                if m['ova']:
                    idx.append({'t': m['titulo'], 'd': donde + ' · OVA',
                                'k': 'OVA', 'u': url(m['ova']), 'f': n})
                for d in m['descargas']:
                    idx.append({'t': d['titulo'], 'd': donde + ' · ' + m['titulo'],
                                'k': d['etiqueta'], 'u': url(d['ruta']), 'f': n})
    for sec in secciones:
        for grupo in sec['grupos']:
            donde = sec['nombre'] + (' · ' + grupo['nombre'] if grupo['nombre'] else '')
            for a in grupo['archivos']:
                idx.append({'t': a['titulo'], 'd': donde,
                            'k': a['etiqueta'], 'u': url(a['ruta']), 'f': 0})
    return idx


def glosa_fase(fase):
    """La glosa de una fase.

    Un programa puede tener varias actividades de proyecto dentro de una misma
    fase; cuando es así, la glosa las anuncia en lugar de mostrar solo la
    primera, que daría una idea incompleta de lo que cubre la fase.
    """
    descripciones = [a['descripcion'] for a in fase['actividades'] if a['descripcion']]
    if not descripciones:
        return ''
    if len(descripciones) == 1:
        return re.sub(r'^AP\d+\.\s*', '', descripciones[0])
    return '{} en esta fase: {}'.format(
        plural(len(descripciones), 'actividad de proyecto', 'actividades de proyecto'),
        ' · '.join(re.sub(r'^AP\d+\.\s*', '', d).rstrip('.') for d in descripciones))


def contar(fase):
    guias = sum(len(a['guias']) for a in fase['actividades'])
    ovas = sum(1 for a in fase['actividades'] for m in a['materiales'] if m['ova'])
    desc = sum(len(m['descargas']) for a in fase['actividades'] for m in a['materiales'])
    desc += sum(1 + len(g['anexos']) for a in fase['actividades'] for g in a['guias'] if g['pdf'])
    return guias, ovas, desc


def reposo(fases, secciones, total):
    """La línea de recuento en reposo: el programa siempre finito y contable."""
    guias = sum(contar(f)[0] for f in fases)
    mats = sum(len(a['materiales']) for f in fases for a in f['actividades'])
    return '{} · {} · {} · {} recursos'.format(
        plural(len(fases), 'fase'), plural(guias, 'guía'),
        plural(mats, 'material', 'materiales'), total)


# --------------------------------------------------------------------------- páginas

def portada(fases, secciones, linea):
    p = ['<main>']
    p.append('<div class="contenedor"><ul class="resultados" id="resultados"></ul></div>')
    p.append('<section class="tablero" aria-label="Fases del proyecto formativo">')
    for fase in fases:
        guias, ovas, desc = contar(fase)
        glosa = glosa_fase(fase)
        p.append(
            '<a class="banda" data-fase-banda="{n}" style="{vars}" href="{href}" '
            'data-lleva-consulta="{href}">'
            '<span class="banda-interior">'
            '<span class="banda-numero">{n}</span>'
            '<span class="banda-cuerpo"><h2 class="banda-nombre">{nombre}</h2>'
            '<p class="banda-glosa">{glosa}</p>'
            '<span class="cifras">'
            '{act}<span><b>{g}</b> {pg}</span><span><b>{o}</b> OVA</span>'
            '<span><b>{d}</b> {pd}</span>'
            '<span class="coincide oculto" data-coincide></span>'
            '</span></span>'
            '<span class="banda-flecha">{flecha}</span>'
            '</span></a>'.format(
                n=fase['numero'], href=url(fase['pagina']), nombre=e(fase['nombre']),
                vars=vars_fase(fase['paleta']),
                act=('<span><b>{}</b> actividades</span>'.format(len(fase['actividades']))
                     if len(fase['actividades']) > 1 else ''),
                glosa=e(glosa), g=guias, o=ovas, d=desc,
                pg='guía' if guias == 1 else 'guías',
                pd='descarga' if desc == 1 else 'descargas',
                flecha=FLECHA))
    p.append('</section>')

    p.append('<div class="contenedor">')
    p.append(rotulo('Documentación del programa'))
    p.append('<div class="filas">')
    for i, sec in enumerate(secciones, 1):
        total = sum(len(g['archivos']) for g in sec['grupos'])
        p.append('<a class="fila" href="informacion-general.html#{ancla}">'
                 '<span class="fila-orden">{i:02d}</span>'
                 '<div class="fila-cuerpo">'
                 '<h3 class="fila-titulo">{nombre}</h3>'
                 '<span class="fila-serie">{n}</span>'
                 '</div><span class="fila-ir">{flecha}</span></a>'.format(
                     i=i, nombre=e(sec['nombre']), n=e(plural(total, 'documento')),
                     ancla=ancla(sec['nombre']), flecha=FLECHA))
    p.append('</div></div></main>')
    return pagina(PROGRAMA['nombre'] + ' · SENA', ''.join(p), reposo=linea,
                  descripcion='Guías, objetos virtuales de aprendizaje y material '
                              'descargable del programa 228183, por fase y actividad '
                              'de proyecto.')


def pagina_fase(fase, fases, linea):
    p = ['<header class="cabecera-fase" style="{}"><div class="contenedor">'.format(
        vars_fase(fase['paleta']))]
    p.append('<nav class="migas"><a href="index.html" data-lleva-consulta="index.html">'
             '{}</a><span>›</span><span>Fase {}</span></nav>'.format(
                 e(PROGRAMA['nombre']), fase['numero']))
    p.append('<div class="titular"><span class="banda-numero">{}</span>'
             '<h1>{}</h1></div>'.format(fase['numero'], e(fase['nombre'])))
    glosa = glosa_fase(fase)
    if glosa:
        p.append('<p class="glosa">{}</p>'.format(e(glosa)))
    p.append('</div></header>')

    p.append('<main><div class="contenedor">')
    p.append('<ul class="resultados" id="resultados"></ul>')
    for act in fase['actividades']:
        # Con una sola actividad, la cabecera de la fase ya dice lo mismo; solo
        # se repite aqui cuando hay varias y hay que distinguirlas.
        if act['descripcion'] and len(fase['actividades']) > 1:
            p.append('<p class="descripcion-actividad">{}</p>'.format(e(act['descripcion'])))
        if act['guias']:
            p.append('<section data-bloque>')
            p.append(rotulo(act['nombre'] + ' · Guías de aprendizaje',
                            plural(len(act['guias']), 'guía')))
            p.append('<div class="filas">')
            for g in act['guias']:
                p.append(fila_guia(g))
            p.append('</div></section>')
        if act['materiales']:
            p.append('<section data-bloque>')
            p.append(rotulo('Materiales de formación',
                            plural(len(act['materiales']), 'material', 'materiales')))
            p.append('<div class="filas">')
            for m in act['materiales']:
                p.append(fila_material(m))
            p.append('</div></section>')

    p.append(rotulo('Ir a'))
    p.append('<div class="salidas">')
    for f in fases:
        if f['numero'] == fase['numero']:
            continue
        p.append('<a class="boton boton-archivo" href="{href}" data-lleva-consulta="{href}">'
                 '<span class="tipo">{n}</span>{nombre}</a>'.format(
                     href=url(f['pagina']), n=f['numero'], nombre=e(f['nombre'])))
    p.append('<a class="boton boton-archivo" href="informacion-general.html" '
             'data-lleva-consulta="informacion-general.html">Documentación</a>')
    p.append('</div></div></main>')

    total_mat = sum(len(a['materiales']) for a in fase['actividades'])
    return pagina('Fase {} · {} — {}'.format(fase['numero'], fase['nombre'], PROGRAMA['nombre']),
                  ''.join(p), fase=str(fase['numero']), reposo=linea,
                  descripcion='{} y {} de la fase de {}.'.format(
                      plural(sum(len(a['guias']) for a in fase['actividades']), 'guía'),
                      plural(total_mat, 'material de formación', 'materiales de formación'),
                      fase['nombre']))


def pagina_documentacion(secciones, fases, linea):
    p = ['<header class="cabecera-fase"><div class="contenedor">']
    p.append('<nav class="migas"><a href="index.html" data-lleva-consulta="index.html">'
             '{}</a><span>›</span><span>Documentación</span></nav>'.format(
                 e(PROGRAMA['nombre'])))
    p.append('<div class="titular"><h1>Documentación del programa</h1></div>')
    p.append('<p class="glosa">Información institucional, cronograma, actividades '
             'iniciales y etapa productiva.</p>')
    p.append('</div></header>')

    p.append('<main><div class="contenedor">')
    p.append('<ul class="resultados" id="resultados"></ul>')
    for sec in secciones:
        total = sum(len(g['archivos']) for g in sec['grupos'])
        p.append('<section data-bloque id="{}">'.format(e(ancla(sec['nombre']))))
        p.append(rotulo(sec['nombre'], plural(total, 'documento')))
        # Cada grupo lleva su propio encabezado y su propia numeración, en vez
        # de repetir el nombre del grupo como etiqueta sobre cada fila.
        for grupo in sec['grupos']:
            if grupo['nombre']:
                p.append('<h3 class="rotulo-sub">{}</h3>'.format(
                    e(NOMBRES_CORREGIDOS.get(grupo['nombre'], grupo['nombre']))))
            p.append('<div class="filas">')
            for i, a in enumerate(grupo['archivos'], 1):
                p.append('<article class="fila" data-buscable="{buscable}">'
                         '<span class="fila-orden">{i:02d}</span><div class="fila-cuerpo">'
                         '<h4 class="fila-titulo">{titulo}</h4>'
                         '<div class="acciones">{chip}</div></div></article>'.format(
                             buscable=e('{} {} {}'.format(a['titulo'], grupo['nombre'] or '',
                                                          sec['nombre'])),
                             i=i, titulo=e(a['titulo']),
                             chip=chip_descarga(a, texto='Descargar')))
            p.append('</div>')
        p.append('</section>')

    p.append(rotulo('Ir a'))
    p.append('<div class="salidas">')
    for f in fases:
        p.append('<a class="boton boton-archivo" href="{href}" data-lleva-consulta="{href}">'
                 '<span class="tipo">{n}</span>{nombre}</a>'.format(
                     href=url(f['pagina']), n=f['numero'], nombre=e(f['nombre'])))
    p.append('</div></div></main>')
    return pagina('Documentación del programa — ' + PROGRAMA['nombre'], ''.join(p),
                  reposo=linea,
                  descripcion='Documentos institucionales, cronograma, actividades '
                              'iniciales y etapa productiva del programa 228183.')


def escribir(nombre, contenido):
    ruta = os.path.join(RAIZ, *nombre.split('/'))
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, 'w', encoding='utf-8', newline='\n') as f:
        f.write(contenido)
    print('  {:30s} {:>6.0f} KB'.format(nombre, len(contenido.encode('utf-8')) / 1024))


def main():
    fases, secciones = recolectar()
    idx = construir_indice(fases, secciones)
    linea = reposo(fases, secciones, len(idx))

    escribir('assets/indice.js',
             'window.INDICE=' + json.dumps(idx, ensure_ascii=False, separators=(',', ':')) + ';\n')
    escribir('index.html', portada(fases, secciones, linea))
    for fase in fases:
        escribir(fase['pagina'], pagina_fase(fase, fases, linea))
    escribir('informacion-general.html', pagina_documentacion(secciones, fases, linea))
    with open(os.path.join(RAIZ, '.nojekyll'), 'w', encoding='utf-8') as f:
        f.write('')

    guias = sum(len(a['guias']) for f in fases for a in f['actividades'])
    ovas = sum(1 for f in fases for a in f['actividades'] for m in a['materiales'] if m['ova'])
    mats = sum(len(a['materiales']) for f in fases for a in f['actividades'])
    print('\n{} fases | {} guias | {} materiales ({} con OVA) | {} recursos indexados'.format(
        len(fases), guias, mats, ovas, len(idx)))


if __name__ == '__main__':
    main()
