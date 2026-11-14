"""Utilidades compartidas: carga del contrato, logging estructurado y rutas."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONTRACT = Path(__file__).parent / "config" / "data_contract.yaml"


@dataclass(frozen=True)
class Contract:
    raw: dict[str, Any]

    @property
    def target(self) -> str:
        return self.raw["objetivo"]["columna"]

    @property
    def columns(self) -> dict[str, dict[str, Any]]:
        return self.raw["columnas"]

    @property
    def pseudonymize(self) -> list[str]:
        return self.raw["identificadores"].get("seudonimizar", [])

    @property
    def drop_pii(self) -> list[str]:
        return self.raw["identificadores"].get("eliminar", [])

    @property
    def prep(self) -> dict[str, Any]:
        return self.raw["preprocesamiento"]

    def cols_of(self, *types: str) -> list[str]:
        return [c for c, s in self.columns.items() if s["tipo"] in types and c != self.target]

    @property
    def critical(self) -> list[str]:
        return [c for c, s in self.columns.items() if s.get("critica")]


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> Contract:
    with open(path, encoding="utf-8") as fh:
        return Contract(yaml.safe_load(fh))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    """Registro estructurado (ISO/IEC 27001:2022, control 8.15). Nunca incluir datos personales."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
