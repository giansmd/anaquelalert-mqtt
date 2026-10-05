# AnaquelAlert — simulación MQTT

Prototipo de laboratorio para representar varios nodos virtuales que publican eventos de detección de faltantes en anaqueles. **Los mensajes son sintéticos**: no son lecturas de sensores físicos ni resultados de un modelo de visión.

## Supuesto provisional de modelado

C2, C3 y C4 representan nodos de observación por zona (salida de una detección de anaquel), no tipos de sensor definidos por el docente. Esto evita añadir sensores de hardware que el informe no eligió. C3 termina abruptamente para observar el mensaje *Last Will and Testament* (LWT) del broker. Ajustar esta abstracción cuando el equipo confirme qué exige la clase.

La ESP32-CAM conserva HTTP para transmitir imágenes; MQTT se usa para telemetría/eventos livianos de zona y disponibilidad de nodos.

## Arquitectura

`C2/C3/C4 (publicadores MQTT) → EMQX → ingestor → MySQL`

- EMQX autentica los cuatro clientes con base de datos integrada y aplica ACL por usuario: C2/C3/C4 solo publican en sus tópicos de zona/disponibilidad; el ingestor solo se suscribe al árbol demo. Sin coincidencia, deniega.
- El usuario y contraseña de MQTT se crean desde variables de entorno en el primer inicio. EMQX guarda usuarios en `emqx_data`; cambiar el `.env` después no rota por sí solo contraseñas ya creadas.
- El stack enlaza puertos del host a `127.0.0.1`; no exponer `1883` sin TLS y credenciales. Para Dokploy, mantener Dashboard y phpMyAdmin privados y configurar acceso MQTT remoto mediante WSS/TLS con proxy/ruteo probado.
- phpMyAdmin en `8080` permite inspeccionar las tablas.
- `models/detection-event.json` muestra el modelo documental NoSQL asociado; es una propuesta lógica, no un MongoDB desplegado.

## Requisitos del laboratorio

La guía pide una VM Linux liviana (usa Ubuntu como ejemplo; VirtualBox es el medio opcional), Docker Engine, CLI y plugin Compose. El servidor remoto por SSH aparece como posibilidad, no como requisito obligatorio.

## Quickstart (stack del laboratorio)

1. Copiar `.env.example` a `.env`; asignar contraseñas aleatorias URL-safe de al menos 24 caracteres a EMQX Dashboard, MySQL y cada usuario MQTT (`C2`, `C3`, `C4`, `INGESTOR`). Los usuarios MQTT deben conservar los nombres de ejemplo porque la ACL está asociada a ellos. No compartir ni versionar `.env`.
2. Con Docker Engine y Docker Compose disponibles, ejecutar `docker compose up --build -d`.
3. Revisar nodos e ingestor: `docker compose logs -f sensor-c2 sensor-c3 sensor-c4 ingestor`.
4. Abrir EMQX Dashboard en `http://localhost:18083` y phpMyAdmin en `http://localhost:8080`.
5. En phpMyAdmin, revisar `anaquelalert.devices` y `anaquelalert.detection_events`.
6. Detener el stack con `docker compose down`. `docker compose down -v` elimina tanto usuarios EMQX como datos MySQL; úsalo solo para reiniciar el laboratorio desde cero.

C2 y C4 publican continuamente. C3 se cae de forma abrupta después de cinco mensajes; EMQX publicará su estado `offline` cuando venza el keepalive. Para reiniciar C3: `docker compose up -d sensor-c3`.

## Modelo relacional

- `devices`: una fila por nodo/zona y su último estado de conexión.
- `detection_events`: un registro por evento, con clave foránea al nodo, instante UTC, estado del anaquel, confianza sintética y payload JSON original.

## Modelo no relacional asociado

`models/detection-event.schema.json` define el esquema documental y `models/detection-event.json` da un ejemplo. Corresponde a una futura colección como `anaquel_events`; el laboratorio no exige desplegar una BD NoSQL y este stack implementa MySQL.

## Componente inteligente (39 palabras; máximo solicitado: 49)

Un modelo de regresión estimará el tiempo hasta el próximo faltante por zona a partir del historial de detecciones y variables temporales. Se comparará con un promedio móvil; si el histórico no basta, la predicción se reportará como experimental.

## Validación del artículo

Registrar versión de EMQX/MySQL, cantidad de publicaciones, entregas QoS 1, latencia observada, estado LWT de C3 y número de filas persistidas. No presentar los datos sintéticos como precisión del detector ni como resultados de campo.

## Prueba local del protocolo (sin Docker)

Esta alternativa valida clientes MQTT y LWT con AMQTT; **no reemplaza** la validación del stack del laboratorio con EMQX/MySQL.

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r requirements.txt -r dev/requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python dev/run_local_demo.py
```

La demo crea C2/C3/C4, registra eventos sintéticos en el monitor y comprueba que el broker publique el LWT de C3 al terminar abruptamente.

## Nota del entorno de desarrollo

En el host de desarrollo actual no hay Docker daemon ni Compose; por eso el stack EMQX/MySQL no puede ejecutarse aquí. La demo local valida el flujo MQTT con AMQTT, pero aún queda ejecutar el stack del laboratorio para comprobar EMQX, MySQL y la persistencia.
