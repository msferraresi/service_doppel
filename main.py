import os
import socket
import sys
import threading
import webbrowser
import uvicorn
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem
from src.db.database import SessionLocal, init_db
from src.db.models import AppSetting
from src.server.app import app

ACTIVE_PORT = 8081


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def get_preferred_port() -> int:
    db = SessionLocal()
    try:
        setting = (
            db.query(AppSetting).filter(AppSetting.key == "preferred_port").first()
        )
        if setting and setting.value.isdigit():
            return int(setting.value)
        # Si no existe aún, guardamos 8081 como default
        db.add(AppSetting(key="preferred_port", value="8081"))
        db.commit()
        return 8081
    finally:
        db.close()


def find_available_port(start_port: int) -> int:
    """Prueba el puerto configurado; si está ocupado, busca el siguiente libre."""
    port = start_port if start_port > 0 else 8081
    for candidate in range(port, port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    # Fallback extremo: deja que el SO asigne uno libre
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def create_default_icon() -> Image.Image:
    img = Image.new("RGB", (64, 64), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    draw.ellipse((10, 10, 54, 54), fill=(56, 189, 248))
    return img


def start_server(port: int):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None, access_log=False)


if __name__ == "__main__":
    init_db()
    preferred = get_preferred_port()
    ACTIVE_PORT = find_available_port(preferred)

    # Guardamos en memoria en FastAPI cuál es el puerto real levantado
    app.state.active_port = ACTIVE_PORT

    threading.Thread(target=start_server, args=(ACTIVE_PORT,), daemon=True).start()

    icon_file = resource_path(os.path.join("resource", "icon.png"))
    try:
        tray_img = Image.open(icon_file)
    except Exception:
        tray_img = create_default_icon()

    icon = Icon(
        "ServiceDoppel",
        tray_img,
        f"ServiceDoppel (Puerto {ACTIVE_PORT})",
        menu=Menu(
            MenuItem(
                f"Abrir Panel (:{ACTIVE_PORT})",
                lambda: webbrowser.open(f"http://localhost:{ACTIVE_PORT}/_admin"),
            ),
            MenuItem("Salir", lambda i: os._exit(0)),
        ),
    )

    icon.run()
