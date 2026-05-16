from fastapi import FastAPI
import psycopg2

app = FastAPI()

conn = psycopg2.connect(
    host="postgres",
    database="monitoring",
    user="alldatasys",
    password="secret"
)

@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/metrics")
def metrics(data: dict):

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO metrics (
            database_name,
            wait_event,
            aas
        )
        VALUES (%s,%s,%s)
    """, (
        data["database"],
        data["wait_event"],
        data["aas"]
    ))

    conn.commit()

    return {"received": True}
