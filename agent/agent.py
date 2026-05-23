import time
import yaml
import requests
import oracledb

from datetime import datetime

# cargar config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

TOKEN = config["token"]
API_URL = config["api_url"]
INTERVAL = config["interval"]

ORACLE_HOST = config["oracle"]["host"]
ORACLE_PORT = config["oracle"]["port"]
ORACLE_SERVICE = config["oracle"]["service"]
ORACLE_USER = config["oracle"]["user"]
ORACLE_PASSWORD = config["oracle"]["password"]

dsn = "{}:{}/{}".format(
    ORACLE_HOST,
    ORACLE_PORT,
    ORACLE_SERVICE
)

while True:

    try:

        conn = oracledb.connect(
            user=ORACLE_USER,
            password=ORACLE_PASSWORD,
            dsn=dsn
        )

        cur = conn.cursor()

        #################################################################
        # WAIT CLASS AAS
        #################################################################

        cur.execute("""
            SELECT
                wait_class,
                ROUND(COUNT(*) / 300, 2) AS aas
            FROM (
                SELECT
                    CASE
                        WHEN wait_class IN ('CPU', 'Other') THEN 'CPU'
                        WHEN wait_class IS NULL THEN 'CPU'
                        ELSE wait_class
                    END AS wait_class
                FROM v$active_session_history
                WHERE
                    sample_time >= SYSDATE - (5/1440)
                    AND session_type = 'FOREGROUND'
            )
            GROUP BY wait_class
            ORDER BY aas DESC
        """)

        rows = cur.fetchall()

        for row in rows:

            wait_class = row[0]
            aas = row[1]

            payload = {
                "database": ORACLE_SERVICE,
                "wait_event": wait_class,
                "aas": float(aas),
                "created_at": str(datetime.now())
            }

            headers = {
                "Authorization": "Bearer {}".format(TOKEN)
            }

            response = requests.post(
                API_URL,
                json=payload,
                headers=headers,
                timeout=10
            )

            print("WAIT CLASS")
            print(payload)
            print(response.status_code)

        #################################################################
        # TOP SQL AAS
        #################################################################
        cur.execute("""
            SELECT *
            FROM (
                 SELECT
                      ash.sql_id,
                      CASE
                          WHEN ash.wait_class IN ('CPU','Other') THEN 'CPU'
                          WHEN ash.wait_class IS NULL THEN 'CPU'
                           ELSE ash.wait_class
                        END AS wait_class,
                        ROUND(COUNT(*) / 300, 4) AS aas,
                        RANK() OVER (
                            ORDER BY COUNT(*) DESC
                        ) AS ranking
                    FROM v$active_session_history ash
                WHERE
                        ash.sample_time >= SYSDATE - (5/1440)
                        AND ash.session_type = 'FOREGROUND'
                        AND ash.sql_id IS NOT NULL
                    GROUP BY
                        ash.sql_id,
                        CASE
                            WHEN ash.wait_class IN ('CPU','Other') THEN 'CPU'
                            WHEN ash.wait_class IS NULL THEN 'CPU'
                            ELSE ash.wait_class
                        END
                     )
            WHERE ranking <= 5
            ORDER BY ranking 
        """)
        sql_rows = cur.fetchall()
        for row in sql_rows:

            sql_id = row[0]
            wait_class = row[1]
            aas = row[2]
            ranking = row[3]

            payload = {
                "database": ORACLE_SERVICE,
                "sql_id": sql_id,
                "wait_class": wait_class,
                "aas": float(aas),
                "ranking": int(ranking),
                "created_at": str(datetime.now())
            }

            headers = {
                "Authorization": "Bearer {}".format(TOKEN)
            }

            response = requests.post(
                API_URL + "/sql",
                json=payload,
                headers=headers,
                timeout=10
            )

            print("TOP SQL")
            print(payload)
            print(response.status_code)

        cur.close()
        conn.close()

    except Exception as e:

        print("ERROR")
        print(str(e))

    time.sleep(INTERVAL)
