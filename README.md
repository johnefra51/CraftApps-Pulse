# CraftApps-Pulse

Tablero que muestra, por cada app de la organización storytold, cuántos commits e issues cerrados se acumulan desde la última release, con un panel por app que guarda el historial completo en números.

Una GitHub Action junta los datos cada 10 minutos y los publica junto a la página. La página solo lee esos archivos, así que quien la visita no gasta su cupo de la API.

## Versiones

- `/` (`index.html`): la principal. Lee los datos que publica la Action, sin gastar API. Si el archivo falta o tiene más de hora y media (por ejemplo, en local), consulta la API pública desde el navegador.
- `/en-vivo.html` (o `/?en-vivo`): el mismo tablero consultando siempre la API desde el navegador (60 consultas por hora por IP). Sirve para ver el dato al momento.
- `/prueba.html`: el mismo tablero con datos inventados, para ver efectos, sonidos y el panel.

Las tres salen del mismo `index.html`. El historial del panel viene siempre del archivo que genera la Action, así que es el mismo en las dos versiones.

## Panel por app

Al tocar una app en el gráfico o su nombre en la tabla se abre un panel con:

- commits sin liberar, issues cerrados desde la release, commits en todo el historial e issues abiertos ahora;
- commits por día, issues reportados y cerrados por día, e issues abiertos a lo largo del tiempo, con las releases marcadas (30 días, 90 días o todo; con más de 120 días se agrupa por semana);
- la lista de releases con los días, commits e issues cerrados de cada ciclo.

Los commits por día se cuentan igual que en el tablero (commits de la rama por defecto según su fecha), y los issues salen de recorrer todos los issues de cada repositorio una vez y después solo los que cambian. La primera vez, el historial completo tarda alrededor de una hora en cargarse; mientras tanto el panel muestra el avance.

## Archivos

- `index.html`: el tablero, en un solo archivo y sin build.
- `prueba.html`: carga `index.html` con datos inventados.
- `scripts/recolectar.py`: junta los datos y escribe `data/estado.json`, `data/historial.json` y `data/estado-recolector.json` (solo usa la librería estándar de Python).
- `.github/workflows/publicar.yml`: corre el recolector y publica el sitio en GitHub Pages.

## Publicarlo en GitHub Pages

1. Sube todos los archivos a la rama `main` de un repositorio, incluida la carpeta `.github`.
2. En el repositorio, ve a **Settings → Pages**.
3. En **Build and deployment → Source**, elige **GitHub Actions**.
4. Ve a la pestaña **Actions**, abre **Publicar tablero** y pulsa **Run workflow** para la primera publicación (también corre solo con cada push a `main`).
5. Cuando termine, la dirección aparece en **Settings → Pages** (`https://<usuario>.github.io/<repositorio>/`).

Después corre solo cada 10 minutos. No hace falta crear ningún token: usa el que GitHub da a cada ejecución, con 1.000 consultas por hora. Una pasada gasta unas 40 consultas más hasta 26 búsquedas (que tienen su propio límite) y, mientras el historial se completa, hasta 150 consultas más dejando siempre margen. Cada pasada continúa desde el historial que publicó la anterior, así que no hace falta guardar nada en el repositorio. Las Actions son gratis en repositorios públicos. GitHub puede atrasar las ejecuciones programadas varios minutos y las pausa si el repositorio pasa 60 días sin actividad; en ese caso se reactivan desde la pestaña Actions.

## Agregar o quitar apps

Edita el arreglo `REPOS` al principio del `<script>` en `index.html`. Ahí también están el umbral de días para marcar una app como atrasada (`DIAS_ATRASO`), las etiquetas que cuentan como bug (`ETIQUETAS_BUG`) y el intervalo de refresco. El recolector lee esa misma lista desde `index.html`, así que no hay que tocar nada más.

## Idiomas

La interfaz está en español, inglés y portugués. Se elige sola según el idioma del navegador (si no es ninguno de los tres, sale en inglés), y se puede cambiar con el selector junto al botón Actualizar; esa elección queda guardada en el navegador. Los textos están en el objeto `TEXTOS` del script.

## Efectos y sonidos

Al refrescar, las barras se vuelven a cargar de izquierda a derecha. Si una app sumó commits o issues cerrados, su barra brilla y aparece un `+N` que vuela hasta el total de arriba, que se ilumina unos segundos. Durante 5 minutos la fila queda marcada con una franja dorada y el `+N` junto al número (también en la tabla), y bajo cada total aparece la lista de apps que sumaron; al tocar una, la página baja hasta esa fila. Mientras dura esa marca, cada refresco o recarga vuelve a mostrar la animación de la suma. Una release nueva ilumina la fila y hace ondular el nombre y la versión; el brillo se va al pasar el mouse por encima o a los 30 minutos.

Los sonidos se generan en el navegador (sin archivos) y suenan bajito. Los navegadores no dejan reproducir audio hasta que la persona toca la página una vez. Los botones con el altavoz y la estrella apagan los sonidos y los efectos; la elección queda guardada. Si el sistema pide reducir el movimiento, los efectos empiezan apagados.

## Página de prueba

`prueba.html` carga el mismo `index.html` pero con datos inventados: no usa la API ni toca los datos guardados del tablero real. Un panel abajo a la derecha tiene botones para sumar commits o issues, publicar una release nueva, refrescar sin cambios, simular falta de cupo o de red y reiniciar los datos. Como lee `index.html`, cualquier cambio en el tablero se ve también en la prueba. Necesita abrirse desde un servidor (GitHub Pages o el comando de abajo), no con doble clic.

## Límite de la API

Publicado con la Action, el tablero no gasta API en el navegador. Sin el archivo (en local, o si la Action se detiene), consulta la API pública: 60 consultas por hora por IP (cada visitante gasta las suyas) y 10 búsquedas por minuto, que van aparte. La primera carga gasta unas 40 consultas. Después, cada 10 minutos y solo con la pestaña visible, pide la lista de la organización (1 consulta) y vuelve a consultar solo las apps que recibieron pushes; las demás, una vez por hora. Con varias pestañas abiertas, solo una consulta. Si se acaba el cupo, se muestra lo guardado y una nota al pie con la hora en que vuelve.

## Probarlo en local

```bash
python -m http.server 8765
```

Luego abre `http://localhost:8765` (consulta la API desde el navegador) o `http://localhost:8765/prueba.html` (datos inventados). Para generar el archivo de datos en local:

```bash
python scripts/recolectar.py
```

Sin token gasta unas 40 consultas de tu cupo de 60 por hora y tarda unos minutos por el límite de búsquedas, así que conviene limitarlo a algunas apps con `REPOS_PRUEBA=photocraft,soundcraft`, o definir `GITHUB_TOKEN` con un token propio. La carpeta `data/` no se sube al repositorio.
