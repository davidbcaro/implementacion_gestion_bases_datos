# -*- coding: utf-8 -*-
"""Descomprime los material.zip (OVAs) del programa en carpetas `ova/` navegables.

Reglas:
  * Deduplica por hash: un OVA repetido en varias fases se extrae una sola vez y
    las demas ubicaciones apuntan al mismo destino (ver herramientas/ovas.json).
  * Normaliza el envoltorio `material/` que traen algunos paquetes.
  * Omite `downloads/material.zip`, que es una copia del propio OVA (~145 MB).

Uso:  python herramientas/extraer_ovas.py [--forzar]
"""
import hashlib
import json
import os
import shutil
import sys
import zipfile

# ===========================================================================
#  OVA QUE NO SE PUBLICAN
#  Los componentes transversales (emprendimiento, comunicacion, medio
#  ambiente, etica, investigacion) son comunes a todos los programas del SENA
#  y suman 285 MB. Se dejan fuera para que el sitio quepa en el limite de 1 GB
#  de GitHub Pages; su material.zip sigue en el disco y basta con quitar un
#  patron de aqui y volver a ejecutar este script para recuperarlos.
# ===========================================================================
import re
NO_PUBLICAR = re.compile(
    r'emprendimiento|negociacion|creatividad|toma de decisiones'
    r'|comportamiento emprendedor|comunicacion oral|medio ambiente'
    r'|salud en el trabajo|derechos fundamentales|ser individuo|ser social'
    r'|entendiendo mi mundo|agente de cambio|fundamentos de investigacion',
    re.I)


RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPA = os.path.join(RAIZ, 'herramientas', 'ovas.json')
TITULOS_JSON = os.path.join(RAIZ, 'herramientas', 'titulos.json')
FORZAR = '--forzar' in sys.argv



def titulo_del_paquete(zip_path):
    """Lee el <title> del index.html que hay dentro del paquete, sin extraerlo."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            idx = next((n for n in z.namelist()
                        if n.endswith('index.html') and n.count('/') <= 1), None)
            if not idx:
                return None
            cabeza = z.read(idx)[:4000].decode('utf-8', 'replace')
    except (zipfile.BadZipFile, OSError, StopIteration):
        return None
    m = re.search(r'<title>(.*?)</title>', cabeza, re.S | re.I)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else None


def hash_archivo(ruta):
    h = hashlib.md5()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


TODOS_LOS_TITULOS = {}


def buscar_zips():
    encontrados = []
    for base, dirs, archivos in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in ('.git', 'ova', 'assets', 'herramientas')]
        if 'material.zip' in archivos:
            p = os.path.join(base, 'material.zip')
            rel = os.path.relpath(base, RAIZ).replace(os.sep, '/')
            t = titulo_del_paquete(p)
            if t:
                TODOS_LOS_TITULOS[rel] = t
            if NO_PUBLICAR.search(os.path.basename(base)):
                continue
            encontrados.append(p)
    return sorted(encontrados)


def prefijo_comun(nombres):
    """Devuelve 'material/' si todo el zip cuelga de esa unica carpeta, o '' si no."""
    if any(n == 'index.html' for n in nombres):
        return ''
    raices = {n.split('/')[0] for n in nombres if n.strip('/')}
    return raices.pop() + '/' if len(raices) == 1 else ''


def extraer(zip_path, destino):
    """Extrae el paquete en `destino`. Marca el final con `.completo` para poder
    reanudar si el proceso se interrumpe. No usa carpetas temporales porque
    Windows bloquea el renombrado de directorios recien escritos."""
    marca = os.path.join(destino, '.completo')
    if os.path.exists(marca) and not FORZAR:
        return False
    shutil.rmtree(destino, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        nombres = [n for n in z.namelist() if not n.startswith('__MACOSX/')]
        pref = prefijo_comun(nombres)
        for info in z.infolist():
            nombre = info.filename
            if nombre.startswith('__MACOSX/'):
                continue
            if nombre.endswith('downloads/material.zip'):
                continue  # copia del propio OVA, redundante con lo ya extraido
            relativo = nombre[len(pref):] if pref and nombre.startswith(pref) else nombre
            if not relativo:
                continue
            salida = os.path.join(destino, *relativo.split('/'))
            if info.is_dir():
                os.makedirs(salida, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(salida), exist_ok=True)
            with z.open(info) as origen, open(salida, 'wb') as fin:
                shutil.copyfileobj(origen, fin)
    with open(marca, 'w', encoding='utf-8') as f:
        f.write(os.path.basename(zip_path))
    return True


def main():
    zips = buscar_zips()
    canonicos = {}
    mapa = {}
    nuevos = intactos = reutilizados = 0
    for zip_path in zips:
        carpeta = os.path.dirname(zip_path)
        rel_carpeta = os.path.relpath(carpeta, RAIZ).replace(os.sep, '/')
        firma = hash_archivo(zip_path)
        if firma in canonicos:
            mapa[rel_carpeta] = canonicos[firma]
            reutilizados += 1
            print('  = {}\n      -> reutiliza {}'.format(rel_carpeta, canonicos[firma]))
            continue
        rel_ova = rel_carpeta + '/ova'
        if extraer(zip_path, os.path.join(carpeta, 'ova')):
            nuevos += 1
            print('  + {}'.format(rel_ova))
        else:
            intactos += 1
            print('  . {} (ya estaba)'.format(rel_ova))
        canonicos[firma] = rel_ova
        mapa[rel_carpeta] = rel_ova
    with open(MAPA, 'w', encoding='utf-8') as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(TITULOS_JSON, 'w', encoding='utf-8') as f:
        json.dump(TODOS_LOS_TITULOS, f, ensure_ascii=False, indent=2, sort_keys=True)
    print('\n{} paquetes | {} extraidos | {} ya estaban | {} reutilizados por duplicado'.format(
        len(zips), nuevos, intactos, reutilizados))


if __name__ == '__main__':
    main()
