import os

import psycopg2
from psycopg2 import errors, sql

from sql_queries import create_table_queries, drop_table_queries

# Conexión a PostgreSQL: variables de entorno con valores por defecto.
# Las claves PG_* coinciden con config/shared_database.env del stack de la academia.
DB_CONFIG = {
    "host": os.getenv("PG_HOST", "127.0.0.1"),
    "port": os.getenv("PG_PORT", "5432"),
    "user": os.getenv("PG_USER", "analytics"),
    "password": os.getenv("PG_PASSWORD", "analytics"),
    "connect_timeout": 5,
}


def database_name():
    """Nombre de la base del data warehouse (configurable con PG_DB)."""
    return os.getenv("PG_DB", "analytics_wh")


def ensure_database(dbname=None):
    """Crea `dbname` si todavía no existe y devuelve su nombre.

    Se conecta a la base administrativa (PG_DB_DEFAULT) porque `CREATE DATABASE`
    no se puede ejecutar dentro de una transacción: la conexión usa autocommit.
    Los nombres se interpolan con `psycopg2.sql.Identifier`, nunca con f-strings.
    """
    dbname = dbname or database_name()
    admin_db = os.getenv("PG_DB_DEFAULT", "postgres")

    if dbname == admin_db:
        raise ValueError(
            f"PG_DB y PG_DB_DEFAULT apuntan a la misma base ({dbname!r}); "
            "elige otra base para el data warehouse."
        )

    conn = psycopg2.connect(dbname=admin_db, **DB_CONFIG)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if cur.fetchone() is None:
                cur.execute(
                    sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8' TEMPLATE template0").format(
                        sql.Identifier(dbname)
                    )
                )
                print(f"Base de datos '{dbname}' creada.")
            else:
                print(f"Base de datos '{dbname}' ya existe.")
    finally:
        conn.close()

    return dbname


def connect(dbname=None):
    """Abre una conexión a la base del data warehouse."""
    return psycopg2.connect(dbname=dbname or database_name(), **DB_CONFIG)


def reset_schema(conn):
    """Elimina y recrea las tablas en una única transacción.

    Si otra sesión mantiene un lock sobre alguna tabla, `lock_timeout` hace
    fallar el reset con un error claro en lugar de quedarse esperando.
    """
    with conn, conn.cursor() as cur:
        cur.execute("SET LOCAL lock_timeout = '5s'")
        for query in drop_table_queries:
            cur.execute(query)
        for query in create_table_queries:
            cur.execute(query)


def main():
    """Crea la base si no existe y deja el esquema del star schema listo.

    - Crea la base de datos configurada en PG_DB (si falta).
    - Elimina las tablas existentes (en orden de dependencias).
    - Crea las 5 tablas del star schema y los índices de la tabla de hechos.
    """
    dbname = ensure_database()
    conn = connect(dbname)
    try:
        reset_schema(conn)
        print(f"Esquema recreado en la base '{dbname}'.")
    except errors.LockNotAvailable as exc:
        raise SystemExit(
            "No se pudo recrear el esquema: otra sesión mantiene bloqueadas las tablas "
            "(por ejemplo, un notebook con una consulta abierta). Ciérrala y vuelve a intentar."
        ) from exc
    finally:
        conn.close()


if __name__ == "__main__":
    main()
