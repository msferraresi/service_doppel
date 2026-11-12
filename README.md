# 🎭 ServiceDoppel

**ServiceDoppel** es un servidor simulador (*Mock Hub*) local y dinámico desarrollado en Python, diseñado para desacoplar el desarrollo y testing de microservicios cuando los servicios aguas arriba aún no están implementados, están inestables o requieren simular respuestas específicas (éxitos, errores de negocio, caídas o latencia).

Funciona como una aplicación de escritorio liviana en segundo plano alojada en la bandeja del sistema (*System Tray*), persistiendo toda su configuración y auditoría de tráfico en una base de datos SQLite local sin necesidad de contenedores Docker ni configuraciones externas.

---

## 🛠️ Stack Tecnológico

* **Backend & API:** FastAPI + Uvicorn
* **Persistencia:** SQLite + SQLAlchemy ORM (`service_doppel.db`)
* **Interfaz de Control:** Panel Web embebido (`static/index.html`) servido en `/_admin`
* **Integración Desktop:** `pystray` + `Pillow` (ejecución silenciosa en el reloj del sistema)
* **Empaquetado:** PyInstaller (`ServiceDoppel.exe` autónomo)

---

## ✨ Características Principales

* **Catch-All Router Dinámico:** Intercepta cualquier ruta y método HTTP (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`), soportando parámetros dinámicos en el path (ej. `/gdr/{nu_ticket}/factura-honorarios`).
* **Validación de Contrato de Entrada:** Permite definir qué parámetros obligatorios debe traer el JSON/Form o si requiere un archivo adjunto (`multipart/form-data`), rechazando automáticamente con `400 Bad Request` si la petición no cumple el contrato.
* **Modos de Respuesta en Vivo:** Alterna el comportamiento de cada endpoint desde el panel web sin reiniciar:
  * 🎯 **Fijo (`fixed`):** Devuelve siempre el escenario seleccionado como activo (ej. `200 OK`).
  * 💥 **Solo Errores (`errors_only`):** Selecciona aleatoriamente entre los escenarios configurados con status $\ge 400$.
  * 🎲 **Aleatorio (`random`):** Alterna entre todos los escenarios disponibles según sus pesos.
  * 🏷️ **Override por Header:** Permite forzar un escenario puntual enviando el header `X-Doppel-Scenario: <nombre_escenario>`.
* **Gestión de Puerto Inteligente:** Intenta levantar en el puerto preferido configurado desde la UI (por defecto `8081`). Si el puerto está ocupado por otra aplicación, busca automáticamente el siguiente puerto disponible (`8082`, `8083`, etc.).
* **Monitor de Tráfico:** Audita en tiempo real las peticiones recibidas, mostrando payloads JSON formateados, campos de formulario y metadatos de archivos adjuntos (nombre, tipo MIME y peso en bytes).

---

## 📂 Estructura del Proyecto

```text
msferraresi-service_doppel/
├── main.py                  # Punto de entrada: inicializa SQLite, Uvicorn y System Tray
├── ServiceDoppel.spec       # Configuración de empaquetado para PyInstaller
├── requirements.txt         # Dependencias del proyecto
├── resource/
│   └── icon.png             # Ícono para la bandeja del sistema
├── static/
│   └── index.html           # Panel de control web (UI)
└── src/
    ├── db/
    │   ├── database.py      # Conexión SQLite compatible con PyInstaller
    │   └── models.py        # Modelos: AppSetting, Service, Endpoint, Scenario, RequestLog
    ├── engine/
    │   ├── matcher.py       # Resolución de rutas por regex y validación de payload
    │   └── dispatcher.py    # Selector de escenarios y simulación de latencia
    └── server/
        └── app.py           # Endpoints administrativos (/_admin/api) y Catch-All Router
```

---

## 🚀 Ejecución y Compilación

### 1. Ejecución en Modo Desarrollo

Con el entorno virtual activo:

```powershell
pip install -r requirements.txt
python main.py
```

Al iniciar, aparecerá el ícono de **ServiceDoppel** junto al reloj de Windows. Haz clic derecho sobre él y selecciona **Abrir Panel (:8081)** (o ingresa a `http://localhost:8081/_admin`).

### 2. Compilar Ejecutable Standalone (`.exe`)

Para generar el ejecutable independiente y correrlo sin tener VS Code ni consolas abiertas:

```powershell
pyinstaller --clean ServiceDoppel.spec
```

El binario se generará en `dist/ServiceDoppel.exe`. Al ejecutarlo, creará el archivo `service_doppel.db` en el mismo directorio donde esté ubicado el `.exe`.

---

## 🔄 Flujo de Uso Rápido

1. Abre el panel web desde el menú del reloj (**Abrir Panel**).
2. En la pestaña **➕ Nuevo Servicio / Endpoint**:
   * Crea un servicio (ej. `siniestro-reclamo`).
   * Registra el endpoint (ej. `POST` `/gdr/terceros/patrocinios`) y sus campos obligatorios.
   * Carga una o más respuestas JSON con su código HTTP (`200`, `400`, `500`) y latencia simulada.
3. En tu aplicación cliente (ej. `application-dev.yml` en Spring Boot o Postman), apunta la URL base hacia `http://localhost:<puerto_activo>`.
4. Controla los escenarios en vivo desde **🎛️ Endpoints y Control** y audita las llamadas entrantes en **🕵️ Monitor de Tráfico**.