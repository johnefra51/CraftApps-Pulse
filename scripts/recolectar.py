# CraftApps-Pulse · recolector de datos para GitHub Actions
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / 'data'
ORG = 'storytold'
API = 'https://api.github.com'
TOKEN = os.environ.get('GITHUB_TOKEN', '')
RESERVA = 250 if TOKEN else 5
TOPE_HISTORIA = int(os.environ.get('TOPE_HISTORIA', '450'))
HORA = 3600
AHORA = datetime.now(timezone.utc)

llamadas = 0
restante = None


def iso(instante):
    return instante.strftime('%Y-%m-%dT%H:%M:%SZ')


def segundos(texto):
    return int(datetime.fromisoformat(texto.replace('Z', '+00:00')).timestamp())


def leer_lista(nombre, html):
    coincidencia = re.search(rf'const {nombre} = \[([\s\S]*?)\];', html)
    if not coincidencia:
        sys.exit(f'No encontré {nombre} en index.html')
    return re.findall(r"'([^']+)'", coincidencia.group(1))


def pedir(url, cabeceras):
    pedido = urllib.request.Request(url, headers=cabeceras)
    with urllib.request.urlopen(pedido, timeout=30) as respuesta:
        return json.load(respuesta), respuesta.headers


def api(ruta):
    global llamadas, restante
    cabeceras = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'craftapps-pulse',
    }
    if TOKEN:
        cabeceras['Authorization'] = f'Bearer {TOKEN}'
    llamadas += 1
    try:
        datos, encabezados = pedir(API + ruta, cabeceras)
    except urllib.error.HTTPError as error:
        if error.headers.get('X-RateLimit-Remaining') is not None:
            restante = int(error.headers['X-RateLimit-Remaining'])
        if error.code == 404:
            return None, error.headers
        raise RuntimeError(f'{ruta}: HTTP {error.code}') from error
    if encabezados.get('X-RateLimit-Remaining') is not None and not ruta.startswith('/search/'):
        restante = int(encabezados['X-RateLimit-Remaining'])
    return datos, encabezados


def contar_por_link(cabeceras, en_pagina):
    ultima = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', cabeceras.get('Link', ''))
    return int(ultima.group(1)) if ultima else en_pagina


def buscar(consulta):
    time.sleep(2.2 if TOKEN else 6.5)
    datos, _ = api('/search/issues?per_page=1&q=' + urllib.parse.quote(consulta))
    return datos['total_count']


def sitio_publicado():
    if os.environ.get('SITIO_URL'):
        return os.environ['SITIO_URL'].rstrip('/') + '/'
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if '/' not in repo:
        return None
    duenio, nombre = repo.split('/', 1)
    return f'https://{duenio.lower()}.github.io/{nombre}/'


def cargar_estado_previo():
    local = DATOS / 'estado-recolector.json'
    if local.exists():
        return json.loads(local.read_text(encoding='utf-8'))
    sitio = sitio_publicado()
    if sitio:
        try:
            datos, _ = pedir(sitio + 'data/estado-recolector.json', {'User-Agent': 'craftapps-pulse'})
            print(f'Continúo desde el historial publicado en {sitio}')
            return datos
        except Exception as error:
            print(f'Sin historial previo ({error}); empiezo de cero')
    return {'version': 1, 'repos': {}}


def cargar_org(repos):
    encontrados = {}
    for pagina in range(1, 4):
        lista, _ = api(f'/orgs/{ORG}/repos?per_page=100&sort=pushed&page={pagina}')
        for repo in lista or []:
            encontrados[repo['name']] = repo
        if not lista or len(lista) < 100 or all(nombre in encontrados for nombre in repos):
            break
    return encontrados


def cargar_repo(nombre, org, etiquetas_bug):
    info = org.get(nombre, {})
    rama = info.get('default_branch') or 'HEAD'
    base = f'/repos/{ORG}/{nombre}'
    latest, _ = api(f'{base}/releases/latest')
    release = {'tag': latest['tag_name'], 'fecha': latest['published_at'], 'url': latest['html_url']} if latest else None

    adelante = None
    if release:
        comparacion, _ = api(f"{base}/compare/{urllib.parse.quote(release['tag'], safe='/')}...{urllib.parse.quote(rama, safe='/')}?per_page=1&page=2")
        adelante = comparacion['ahead_by'] if comparacion else None


    cerrados = bugs = None
    if release:
        consulta = f"repo:{ORG}/{nombre} is:issue is:closed closed:>={release['fecha']}"
        cerrados = buscar(consulta)
        etiquetas = ','.join(f'"{etiqueta}"' for etiqueta in etiquetas_bug)
        bugs = buscar(f'{consulta} label:{etiquetas}') if cerrados else 0

    return {
        'release': release,
        'adelante': adelante,
        'commits30': None,
        'cerrados': cerrados,
        'bugs': bugs,
        'rama': info.get('default_branch'),
        'estrellas': info.get('stargazers_count'),
        'forks': info.get('forks_count'),
        'url': info.get('html_url'),
        'empujado': info.get('pushed_at'),
        'creado': info.get('created_at'),
    }


def contar_dia(nombre, dia):
    siguiente = dia + timedelta(days=1)
    lista, cabeceras = api(f'/repos/{ORG}/{nombre}/commits?since={dia}T00:00:00Z&until={siguiente}T00:00:00Z&per_page=1')
    return contar_por_link(cabeceras, len(lista or []))


def guardar_issues(estado, lista, etiquetas_bug):
    for issue in lista:
        if 'pull_request' in issue:
            continue
        cerrado = segundos(issue['closed_at']) if issue.get('state') == 'closed' and issue.get('closed_at') else 0
        bug = int(any(etiqueta['name'].lower() in etiquetas_bug for etiqueta in issue.get('labels', [])))
        estado['issues'][str(issue['number'])] = [segundos(issue['created_at']), cerrado, bug]


def tareas_de_historia(nombre, estado, creado, etiquetas_bug):
    ayer = AHORA.date() - timedelta(days=1)
    ahora = int(AHORA.timestamp())
    base = f'/repos/{ORG}/{nombre}'

    def issues_recientes():
        pagina = 1
        while True:
            lista, _ = api(f"{base}/issues?state=all&since={iso(datetime.fromtimestamp(estado['issuesHasta'], timezone.utc))}&sort=updated&direction=asc&per_page=100&page={pagina}")
            guardar_issues(estado, lista or [], etiquetas_bug)
            if not lista or len(lista) < 100:
                break
            pagina += 1
        estado['issuesHasta'] = ahora - 120

    def issues_pagina():
        if estado.get('issuesDesde') is None:
            estado['issuesDesde'] = ahora - 120
            ultimo, _ = api(f'{base}/issues?state=all&sort=created&direction=desc&per_page=1')
            estado['issuesMaximo'] = ultimo[0]['number'] if ultimo else 0
        ruta = estado.get('issuesSiguiente') or f'{base}/issues?state=all&sort=created&direction=asc&per_page=100'
        lista, cabeceras = api(ruta)
        guardar_issues(estado, lista or [], etiquetas_bug)
        if lista:
            estado['issuesVisto'] = max(estado.get('issuesVisto', 0), lista[-1]['number'])
        siguiente = re.search(r'<([^>]+)>;\s*rel="next"', cabeceras.get('Link', ''))
        if not lista or not siguiente:
            estado['issuesSiguiente'] = None
            estado['issuesCompleto'] = True
            estado['issuesHasta'] = estado['issuesDesde']
        else:
            estado['issuesSiguiente'] = siguiente.group(1).replace(API, '')
            pendientes.append(issues_pagina)

    def contar(dia):
        estado['commits'][dia.isoformat()] = [contar_dia(nombre, dia), ahora]

    urgentes = []
    pendientes = []
    if estado.get('issuesCompleto'):
        urgentes.append(issues_recientes)

    dia = creado
    while dia <= ayer:
        guardado = estado['commits'].get(dia.isoformat())
        fin_del_dia = int(datetime.combine(dia + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp())
        reciente = (ayer - dia).days < 30
        if not guardado or guardado[1] < fin_del_dia + HORA or (reciente and ahora - guardado[1] > 12 * HORA):
            pendientes.append(lambda dia=dia: contar(dia))
        dia += timedelta(days=1)
    if not estado.get('issuesCompleto'):
        pendientes.append(issues_pagina)
    return urgentes, pendientes


def armar_historia(estado, creado):
    ayer = AHORA.date() - timedelta(days=1)
    dias = max(0, (ayer - creado).days + 1)
    indice = lambda instante: (datetime.fromtimestamp(instante, timezone.utc).date() - creado).days
    commits = [estado['commits'].get((creado + timedelta(days=i)).isoformat(), [None])[0] for i in range(dias)]
    reportados = [0] * dias
    cerrados = [0] * dias
    for abierto, cerrado, _ in estado['issues'].values():
        if 0 <= indice(abierto) < dias:
            reportados[indice(abierto)] += 1
        if cerrado and 0 <= indice(cerrado) < dias:
            cerrados[indice(cerrado)] += 1
    abiertos = []
    acumulado = 0
    for i in range(dias):
        acumulado += reportados[i] - cerrados[i]
        abiertos.append(acumulado)
    completo_issues = bool(estado.get('issuesCompleto'))
    progreso = 1 if completo_issues else round(min(1, estado.get('issuesVisto', 0) / max(1, estado.get('issuesMaximo', 1))), 2)
    return {
        'desde': creado.isoformat(),
        'commits': commits,
        'reportados': reportados,
        'cerrados': cerrados,
        'abiertos': abiertos,
        'releases': estado.get('releases', []),
        'completo': {'commits': None not in commits, 'issues': completo_issues},
        'progreso': {'issues': progreso},
    }


def main():
    html = (RAIZ / 'index.html').read_text(encoding='utf-8')
    repos = leer_lista('REPOS', html)
    etiquetas_bug = [etiqueta.lower() for etiqueta in leer_lista('ETIQUETAS_BUG', html)]
    solo = os.environ.get('REPOS_PRUEBA')
    if solo:
        repos = [nombre for nombre in repos if nombre in solo.split(',')]

    previo = cargar_estado_previo()
    org = cargar_org(repos)

    resultado = {}
    errores = 0
    for nombre in repos:
        try:
            resultado[nombre] = cargar_repo(nombre, org, etiquetas_bug)
            print(f"{nombre}: {resultado[nombre]['adelante']} commits desde la release, {resultado[nombre]['cerrados']} issues cerrados")
        except Exception as error:
            errores += 1
            resultado[nombre] = {'error': str(error)}
            print(f'{nombre}: {error}', file=sys.stderr)
    if errores == len(repos):
        sys.exit('No pude leer ninguna app.')

    estados = previo.setdefault('repos', {})
    urgentes = []
    colas = []
    for nombre in repos:
        datos = resultado[nombre]
        if 'error' in datos or not datos.get('creado'):
            continue
        estado = estados.setdefault(nombre, {})
        estado.setdefault('commits', {})
        estado.setdefault('issues', {})
        tag = datos['release']['tag'] if datos['release'] else None
        if estado.get('releaseActual', '') != tag or AHORA.timestamp() - estado.get('releasesEn', 0) > HORA:
            lista, _ = api(f'/repos/{ORG}/{nombre}/releases?per_page=100')
            estado['releases'] = sorted(
                [[r['tag_name'], r['published_at']] for r in lista or [] if not r.get('draft') and r.get('published_at')],
                key=lambda release: release[1],
            )
            estado['releaseActual'] = tag
            estado['releasesEn'] = int(AHORA.timestamp())
        creado = date.fromisoformat(datos['creado'][:10])
        propias, pendientes = tareas_de_historia(nombre, estado, creado, etiquetas_bug)
        urgentes += propias
        colas.append(pendientes)

    def correr(tarea):
        if (restante or 0) <= RESERVA:
            return False
        try:
            tarea()
            return True
        except Exception as error:
            print(f'Historial en pausa hasta la próxima ejecución: {error}', file=sys.stderr)
            return False

    for tarea in urgentes:
        if not correr(tarea):
            break
    tope = min(TOPE_HISTORIA, max(0, (restante or 0) - RESERVA))
    gastadas = 0
    while gastadas < tope and any(colas):
        for cola in colas:
            if cola and gastadas < tope:
                if not correr(cola.pop(0)):
                    tope = 0
                    break
                gastadas += 1

    historia = {}
    for nombre in repos:
        datos = resultado[nombre]
        if 'error' not in datos and nombre in estados and datos.get('creado'):
            historia[nombre] = armar_historia(estados[nombre], date.fromisoformat(datos['creado'][:10]))
            datos['commits30'] = sum(c or 0 for c in historia[nombre]['commits'][-30:])

    DATOS.mkdir(parents=True, exist_ok=True)
    generado = iso(datetime.now(timezone.utc))
    escribir = lambda archivo, contenido: (DATOS / archivo).write_text(json.dumps(contenido, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    escribir('estado.json', {'generado': generado, 'repos': resultado})
    escribir('historial.json', {'generado': generado, 'repos': historia})
    escribir('estado-recolector.json', previo)
    faltan = sum(len(cola) for cola in colas)
    print(f'Listo: {llamadas} consultas, {faltan} tareas de historial pendientes, cupo restante {restante}')


if __name__ == '__main__':
    main()
