from txt2sql.config import load_settings
from txt2sql.db import connect, execute_query

s = load_settings()
with connect(s.database_url) as c:
    rows = execute_query(
        c,
        """
        SELECT COUNT(*) AS n,
               ROUND(AVG("A14")::numeric, 1) AS avg_area,
               ROUND(AVG("A16")::numeric, 1) AS avg_height,
               ROUND(MIN("A14")::numeric, 1) AS min_area,
               ROUND(MAX("A14")::numeric, 1) AS max_area,
               ROUND(AVG("A26")::numeric, 1) AS avg_floors,
               ROUND(AVG("A12")::numeric, 1) AS avg_bldg_area,
               ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "A14")::numeric, 1) AS med_area
        FROM "AL_D010_26_20250704"
        WHERE "A4" LIKE '%구서동%'
          AND "A9" = '공동주택'
        """,
    )
    print("apt:", rows)
    rows = execute_query(
        c,
        """
        SELECT "A11" AS structure, COUNT(*) AS n
        FROM "AL_D010_26_20250704"
        WHERE "A4" LIKE '%구서동%' AND "A9" = '공동주택'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 5
        """,
    )
    print("struct:", rows)
