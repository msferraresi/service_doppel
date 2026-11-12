from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from src.db.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)  # ej: siniestro-reclamo
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

    endpoints = relationship(
        "Endpoint", back_populates="service", cascade="all, delete-orphan"
    )


class Endpoint(Base):
    __tablename__ = "endpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    method = Column(
        String(10), nullable=False, default="POST"
    )  # GET, POST, PUT, DELETE
    path_pattern = Column(
        String(255), nullable=False
    )  # ej: /gdr/{nu_ticket}/factura-honorarios
    mode = Column(String(20), default="fixed")  # "fixed", "random", "header_driven"
    active_scenario_id = Column(
        Integer, nullable=True
    )  # ID del escenario activo si mode="fixed"

    service = relationship("Service", back_populates="endpoints")
    scenarios = relationship(
        "Scenario", back_populates="endpoint", cascade="all, delete-orphan"
    )
    logs = relationship(
        "RequestLog", back_populates="endpoint", cascade="all, delete-orphan"
    )


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint_id = Column(Integer, ForeignKey("endpoints.id"), nullable=False)
    name = Column(
        String(100), nullable=False
    )  # ej: "success_200", "error_400_falta_reclamo"
    status_code = Column(Integer, default=200)
    delay_ms = Column(Integer, default=0)
    weight = Column(Float, default=1.0)  # Para modo random
    response_body = Column(JSON, nullable=False, default=dict)

    endpoint = relationship("Endpoint", back_populates="scenarios")


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    endpoint_id = Column(Integer, ForeignKey("endpoints.id"), nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)
    method = Column(String(10), nullable=False)
    path = Column(String(255), nullable=False)
    headers = Column(JSON, nullable=True)
    query_params = Column(JSON, nullable=True)
    form_data = Column(JSON, nullable=True)  # Campos de texto del form
    files_info = Column(JSON, nullable=True)  # Nombre de archivo PDF, size, mime
    raw_body = Column(String, nullable=True)  # Si vino JSON crudo
    matched_scenario_id = Column(Integer, nullable=True)

    endpoint = relationship("Endpoint", back_populates="logs")
