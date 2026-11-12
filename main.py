import uvicorn

from src.db.database import init_db

if __name__ == "__main__":
    init_db()
    # Levantamos en el puerto 8080 o el que suela usar siniestro-reclamo en tu entorno local
    uvicorn.run("src.server.app:app", host="0.0.0.0", port=8080, reload=True)
