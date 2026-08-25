from txt2sql.config import load_settings
from txt2sql.db import connect, execute_query

s = load_settings()
with connect(s.database_url) as c:
    rows = execute_query(
        c,
        """
        SELECT column_name, display_name
        FROM column_metadata
        WHERE table_name = 'AL_D010_26_20250704'
        ORDER BY column_name
        """,
    )
    for r in rows:
        print(r["column_name"], r["display_name"])
    top = execute_query(
        c,
        """
        SELECT "A0","A1","A4","A5","A9","A12","A14","A16","A19","A25","A26"
        FROM "AL_D010_26_20250704"
        WHERE ("A4" LIKE '% 구서동' OR "A4" = '구서동') AND "A9" = '공동주택'
        ORDER BY "A12" DESC NULLS LAST
        LIMIT 1
        """,
    )
    print("TOP:", top)
