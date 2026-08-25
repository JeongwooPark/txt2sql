from txt2sql.config import load_settings
from txt2sql.db import connect, execute_query

s = load_settings()
with connect(s.database_url) as c:
    rows = execute_query(
        c,
        """
        SELECT dong, COUNT(*) AS gus, string_agg(gu, ', ') AS gu_list
        FROM (
          SELECT
            regexp_replace("A4", '^.* ', '') AS dong,
            (regexp_match("A4", '([가-힣]+구)'))[1] AS gu
          FROM "AL_D010_26_20250704"
          WHERE "A4" LIKE '%동'
          GROUP BY 1, 2
        ) t
        GROUP BY dong
        HAVING COUNT(*) > 1
        ORDER BY 2 DESC
        LIMIT 20
        """,
    )
    print("multi-gu dongs:", rows)
    for place in ("서동", "중동", "하동", "덕천동"):
        rows = execute_query(
            c,
            f"""
            SELECT DISTINCT "A4" AS place, COUNT(*) AS n
            FROM "AL_D010_26_20250704"
            WHERE "A4" LIKE '% {place}' OR "A4" = '{place}'
            GROUP BY 1
            """,
        )
        print("exact", place, rows)
