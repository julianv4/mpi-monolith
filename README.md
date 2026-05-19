# MPI Monolith — Trabajo Práctico: Sistemas Distribuidos

Simulación del monolito de "Market-Place-Inc" con FastAPI, test de carga y análisis del teorema CAP.

## Stack

- Python 3.9
- FastAPI + Uvicorn
- MySQL + aiomysql
- SQLAlchemy 2.0 (async)
- Locust (test de carga)

---

## Configuración

### 1. Instalar MySQL

```bash
brew install mysql
brew services start mysql
mysql_secure_installation
```

### 2. Crear la base de datos

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS monolito CHARACTER SET utf8mb4;"
```

### 3. Instalar dependencias

```bash
pip3 install -r requirements.txt
pip3 install cryptography
```

### 4. Configurar la contraseña de la base de datos

En `main.py`, actualizá esta línea con tu contraseña de MySQL:

```python
DATABASE_URL = "mysql+aiomysql://root:TU_CONTRASEÑA@localhost/monolito"
```

### 5. Levantar el servidor

```bash
python3 -m uvicorn main:app --reload --port 8000
```

La documentación de la API está disponible en: http://localhost:8000/docs

### 6. Insertar datos de prueba. Se incluye un ejemplo usado

```bash
mysql -u root -p monolito
```

```sql
INSERT INTO productos (nombre, precio, stock) VALUES ('Cellphone', 999.99, 10000);
exit
```

---

## Test de carga

Correr con Locust (60 segundos, 50 usuarios concurrentes):

```bash
python3 -m locust -f locustfile.py --headless -u 50 -r 5 --host http://localhost:8000 --csv=resultados --run-time 60s
```

Los resultados se guardan en `resultados_stats.csv` y `resultados_failures.csv`.

---

## Resultados observados

| Endpoint | Latencia promedio (inicio) | Latencia promedio (bajo carga) | Fallos |
|---|---|---|---|
| `POST /orders` | ~3000ms | ~4700ms | 100% |
| `GET /products` | ~5ms | ~1700ms | 0% |
| `GET /health` | <20ms | <20ms | 0% |

### Conclusión

`POST /orders` simula un pago lento (3 segundos con `asyncio.sleep(3)`).
Durante ese tiempo, MySQL (InnoDB) mantiene un lock activo sobre la fila del producto comprado.

`GET /products` es un endpoint de lectura simple que no tiene nada que ver con pedidos ni pagos.
Sin embargo, su latencia promedio pasó de **5ms a ~1700ms** bajo carga — porque ambos endpoints
comparten el mismo pool de conexiones a la base de datos.

Esto reproduce el problema central del incidente del Hot Sale de MPI: el catálogo de productos
cayó no por un bug en el código del catálogo, sino porque compartía la base de datos con el módulo de pagos.

El error `QueuePool limit exceeded` en `POST /orders` muestra que el pool de conexiones
(5 + 10 = 15 conexiones) se agota cuando hay requests concurrentes manteniendo cada uno
una conexión abierta durante 3 segundos.

`GET /health` nunca toca la base de datos y se mantiene por debajo de los 20ms en todo momento —
lo que confirma que el problema es el acoplamiento a través de la DB, no la capacidad del servidor.
