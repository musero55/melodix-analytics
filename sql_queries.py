# DROP TABLES

songplay_table_drop = "DROP TABLE IF EXISTS songplays"
user_table_drop = "DROP TABLE IF EXISTS users"
song_table_drop = "DROP TABLE IF EXISTS songs"
artist_table_drop = "DROP TABLE IF EXISTS artists"
time_table_drop = "DROP TABLE IF EXISTS time"

# CREATE TABLES
#
# Orden importante: las tablas de dimensiones se crean antes que la tabla de
# hechos porque `songplays` declara claves foráneas hacia ellas.

artist_table_create = ("""
CREATE TABLE IF NOT EXISTS artists (
    artist_id varchar PRIMARY KEY,
    name varchar,
    location varchar,
    latitude numeric,
    longitude numeric
);
""")

song_table_create = ("""
CREATE TABLE IF NOT EXISTS songs (
    song_id varchar PRIMARY KEY,
    title varchar,
    artist_id varchar NOT NULL,
    year int,
    duration numeric
);
""")

user_table_create = ("""
CREATE TABLE IF NOT EXISTS users (
    user_id int PRIMARY KEY,
    first_name varchar,
    last_name varchar,
    gender varchar,
    level varchar
);
""")

time_table_create = ("""
CREATE TABLE IF NOT EXISTS time (
    start_time timestamp PRIMARY KEY,
    hour int,
    day int,
    week int,
    month int,
    year int,
    weekday int
);
""")

# La surrogate key la genera PostgreSQL (IDENTITY), no el ETL. La unicidad
# lógica se garantiza con la clave natural del evento: un usuario no puede
# tener dos eventos en el mismo instante y en la misma sesión. Así el ETL es
# idempotente aunque se ejecute en otro orden, en otro proceso o desde el
# notebook, sin depender de un contador en memoria.
songplay_table_create = ("""
CREATE TABLE IF NOT EXISTS songplays (
    songplay_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    start_time timestamp NOT NULL REFERENCES time(start_time),
    user_id int NOT NULL REFERENCES users(user_id),
    level varchar,
    song_id varchar REFERENCES songs(song_id),
    artist_id varchar REFERENCES artists(artist_id),
    session_id int NOT NULL,
    location varchar,
    user_agent varchar,
    CONSTRAINT songplays_event_unique UNIQUE (start_time, user_id, session_id)
);
""")

# Índices sobre las claves foráneas de la tabla de hechos: aceleran los JOIN
# y los filtros más habituales del análisis. `start_time` no necesita un índice
# propio: es la primera columna del índice único de la clave natural.
songplay_user_id_index_create = "CREATE INDEX IF NOT EXISTS songplays_user_id_idx ON songplays (user_id)"
songplay_song_id_index_create = "CREATE INDEX IF NOT EXISTS songplays_song_id_idx ON songplays (song_id)"
songplay_artist_id_index_create = "CREATE INDEX IF NOT EXISTS songplays_artist_id_idx ON songplays (artist_id)"

# INSERT RECORDS

# La clave natural del evento es (start_time, user_id, session_id). Si el
# evento ya existe pero se cargó antes de tener el catálogo completo (por
# ejemplo desde `etl.ipynb`, que procesa una sola canción), completamos los
# ids de dimensión con COALESCE en lugar de descartar la fila: así el orden de
# ejecución no cambia el resultado y el ETL converge al mismo estado.
songplay_table_insert = ("""
INSERT INTO songplays (start_time, user_id, level, song_id, artist_id, session_id, location, user_agent)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (start_time, user_id, session_id)
DO UPDATE
    SET song_id = COALESCE(EXCLUDED.song_id, songplays.song_id),
        artist_id = COALESCE(EXCLUDED.artist_id, songplays.artist_id)
    WHERE (songplays.song_id IS NULL AND EXCLUDED.song_id IS NOT NULL)
       OR (songplays.artist_id IS NULL AND EXCLUDED.artist_id IS NOT NULL)
""")

user_table_insert = ("""
INSERT INTO users (user_id, first_name, last_name, gender, level)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (user_id)
DO UPDATE
    SET first_name = EXCLUDED.first_name,
        last_name = EXCLUDED.last_name,
        gender = EXCLUDED.gender,
        level = EXCLUDED.level;
""")

song_table_insert = ("""
INSERT INTO songs (song_id, title, artist_id, year, duration)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (song_id)
DO NOTHING
""")

artist_table_insert = ("""
INSERT INTO artists (artist_id, name, location, latitude, longitude)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (artist_id)
DO NOTHING
""")


time_table_insert = ("""
INSERT INTO time (start_time, hour, day, week, month, year, weekday)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (start_time)
DO NOTHING
""")

# FIND SONGS
#
# `duration` se compara con tolerancia (0.01 s): en datos reales el float del
# log y el numeric del catálogo no siempre son exactamente iguales, y una
# igualdad estricta perdería matches válidos. `LIMIT 1` evita que `fetchone()`
# dependa del plan de ejecución si hubiera más de una fila candidata.

song_select = ("""
SELECT song_id, songs.artist_id FROM songs
JOIN artists ON artists.artist_id = songs.artist_id
WHERE title = %s
AND name = %s
AND ABS(duration - %s) < 0.01
ORDER BY song_id
LIMIT 1;
""")

# QUERY LISTS

drop_table_queries = [songplay_table_drop, time_table_drop, user_table_drop, song_table_drop, artist_table_drop]
create_table_queries = [
    artist_table_create,
    song_table_create,
    user_table_create,
    time_table_create,
    songplay_table_create,
    songplay_user_id_index_create,
    songplay_song_id_index_create,
    songplay_artist_id_index_create,
]
