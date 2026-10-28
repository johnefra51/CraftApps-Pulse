# CraftApps-Pulse

Tablero que muestra, por cada app de la organización storytold, cuántos commits e issues cerrados se acumulan desde la última release, con un panel por app que guarda el historial completo en números.

## Cómo funciona (híbrido)

- **Historial (días completos hasta ayer):** una GitHub Action corre una vez al día y guarda el historial de cada app y una foto del estado de ese momento. Las fechas son en UTC.
- **Hoy, en vivo:** el navegador consulta la API pública de GitHub, sin token. Parte de la foto del día y solo vuelve a consultar las apps que recibieron pushes desde entonces (y todas cada 6 horas, por si acaso).
- **Mismo método en los dos lados:** lo de hoy se cuenta exactamente como lo cuenta la Action, solo que hasta ese momento; al terminar el día, la Action guarda ese mismo conteo ya completo. Además recuenta los últimos 30 días en cada pasada, porque un merge puede meter commits con fechas anteriores.
- **Lo guardado en el navegador:** cada navegador guarda lo último que consultó, así que al volver muestra eso de inmediato y solo pide lo que falta.

### Cuándo consulta

- Como mucho una vez cada **15 minutos** por navegador.
- **En vivo** (interruptor junto al botón): se actualiza solo cada 15 minutos mientras la pestaña está visible.
- Sin **En vivo**: se actualiza al recargar la página o con el botón **Actualizar**, si ya pasaron los 15 minutos. Si todavía no pasaron, la página solo se redibuja con lo guardado, sin consultar ni avisar nada.
- Al pie, una línea dice en cuántos minutos se puede volver a actualizar. Se recalcula en cada refresco; no corre en vivo.
- El cupo de 60 consultas por hora por IP se reparte entre las rondas que quedan antes de que se renueve, dejando siempre una reserva, así que la página nunca pasa el límite. La primera consulta del día puede usar más para ponerse al día. Las búsquedas de issues tienen su propio límite (10 por minuto) y la página las espacia sola.

## Versiones

- `/` (`index.html`): el tablero híbrido.
- `/prueba.html`: el mismo tablero con datos inventados, para ver efectos, sonidos y el panel. Ahí la espera entre consultas es de 20 segundos en vez de 15 minutos.

## Panel por app

Al tocar una app en el gráfico o su nombre en la tabla se abre un panel con:

- commits sin liberar, issues cerrados desde la release, commits en todo el historial e issues abiertos ahora;
- commits por día, issues reportados y cerrados por día, e issues abiertos a lo largo del tiempo, con las releases marcadas (30 días, 90 días o todo; con más de 120 días se agrupa por semana);
- la lista de releases con los días, commits e issues cerrados de cada ciclo.

Los días anteriores salen del historial guardado. El día de hoy se pide en vivo al abrir el panel (1 consulta y 3 búsquedas, como mucho cada 15 minutos por app) y queda guardado en el navegador.

## Desde tu última visita

Cada navegador recuerda lo último que vio. Si vuelves después de un rato, la página trae los datos actuales de una vez, repite las animaciones de lo que cambió (sumas, releases nuevas) y muestra arriba un resumen: commits nuevos, issues cerrados y releases publicadas desde tu última visita. Se cierra con **Entendido**.

## Archivos

- `index.html`: el tablero, en un solo archivo y sin build.
- `prueba.html`: carga `index.html` con datos inventados.
- `scripts/recolectar.py`: junta los datos y escribe `data/estado.json` (la foto del día), `data/historial.json` (el historial hasta ayer) y `data/estado-recolector.json` (su avance), solo con la librería estándar de Python.
- `.github/workflows/publicar.yml`: corre el recolector una vez al día (00:17 UTC) y con cada push a `main`, y publica el sitio en GitHub Pages.

## Publicarlo en GitHub Pages

1. Sube todos los archivos a la rama `main` de un repositorio, incluida la carpeta `.github`.
2. En **Settings → Pages → Build and deployment → Source**, elige **GitHub Actions**.
3. En **Actions → Publicar tablero**, pulsa **Run workflow** para la primera publicación.
4. La dirección aparece en **Settings → Pages** (`https://<usuario>.github.io/<repositorio>/`).

La Action usa el token que GitHub da a cada ejecución; no hace falta crear ninguno. GitHub puede atrasar la ejecución diaria, pero no importa: lo de hoy siempre se consulta en vivo. Si el repositorio pasa 60 días sin actividad, GitHub pausa la programación; se reactiva desde la pestaña Actions.

## Agregar o quitar apps

Edita el arreglo `REPOS` al principio del `<script>` en `index.html`. Ahí también están el umbral de días para marcar una app como atrasada (`DIAS_ATRASO`), las etiquetas que cuentan como bug (`ETIQUETAS_BUG`) y el intervalo de refresco. El recolector lee esa misma lista desde `index.html`, así que no hay que tocar nada más.

## Idiomas

La interfaz está en español, inglés y portugués. Se elige sola según el idioma del navegador (si no es ninguno de los tres, sale en inglés), y se puede cambiar con el selector junto al botón Actualizar; esa elección queda guardada en el navegador. Los textos están en el objeto `TEXTOS` del script.

## Efectos y sonidos

Al refrescar, las barras se vuelven a cargar de izquierda a derecha. Si una app sumó commits o issues cerrados, su barra brilla y aparece un `+N` que vuela hasta el total de arriba, que se ilumina unos segundos. Durante 5 minutos la fila queda marcada con una franja dorada y el `+N` junto al número (también en la tabla), y bajo cada total aparece la lista de apps que sumaron; al tocar una, la página baja hasta esa fila. Mientras dura esa marca, cada refresco o recarga vuelve a mostrar la animación de la suma. Una release nueva ilumina la fila y hace ondular el nombre y la versión; el brillo se va al pasar el mouse por encima o a los 30 minutos.

Los sonidos se generan en el navegador (sin archivos) y suenan bajito. Los navegadores no dejan reproducir audio hasta que la persona toca la página una vez. Los botones con el altavoz y la estrella apagan los sonidos y los efectos; la elección queda guardada. Si el sistema pide reducir el movimiento, los efectos empiezan apagados.

## Página de prueba

`prueba.html` carga el mismo `index.html` pero con datos inventados: no usa la API ni toca los datos guardados del tablero real. Un panel abajo a la derecha tiene botones para sumar commits o issues, publicar una release nueva, refrescar respetando la espera (para ver qué pasa si todavía no se puede consultar), simular falta de cupo o de red y reiniciar los datos. Los botones que cambian datos se saltan la espera para poder probar seguido. Como lee `index.html`, cualquier cambio en el tablero se ve también en la prueba. Necesita abrirse desde un servidor (GitHub Pages o el comando de abajo), no con doble clic.

## Probarlo en local

```bash
python -m http.server 8765
```

Luego abre `http://localhost:8765` (consulta la API desde el navegador) o `http://localhost:8765/prueba.html` (datos inventados). Para generar el archivo de datos en local:

```bash
python scripts/recolectar.py
```

Sin token gasta las consultas de tu propio cupo de 60 por hora (unas 30 más el historial) y tarda unos minutos por el límite de búsquedas, así que conviene limitarlo a algunas apps con `REPOS_PRUEBA=photocraft,soundcraft`, o definir `GITHUB_TOKEN` con un token propio. La carpeta `data/` no se sube al repositorio.
