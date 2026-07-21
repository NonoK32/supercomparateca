"""Similitud de texto para sugerir producto a partir de una línea de ticket.

Implementa el punto 3 de §5bis (Fase 2 / EPIC 10 / FR9): cuando el texto de la
línea no coincide *exactamente* con ningún alias del supermercado, se busca el
alias más parecido. Por encima de `umbral_auto` se asigna solo; entre
`umbral_sugerencia` y `umbral_auto` queda como sugerencia para que el usuario
confirme.

El motor de similitud está deliberadamente aislado en `_similitud`: usa
`difflib` (stdlib, sin dependencias). Cambiarlo por rapidfuzz u otro es
reescribir solo esa función, siempre que siga devolviendo un score 0.0–1.0.
"""

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .config import settings


@dataclass
class Candidato:
    """Un producto propuesto para una línea, con su score y el alias que lo motiva."""

    producto_id: int
    texto_alias: str
    score: float


def normalizar(texto: str) -> str:
    """Forma canónica para comparar: sin tildes, minúsculas, tokens ordenados.

    Ordenar los tokens hace la comparación insensible al orden de las palabras
    ("LECHE SEMI 1L" vs "1L LECHE SEMI"), que es la principal debilidad de una
    comparación de secuencias pura.
    """
    sin_tildes = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    tokens = sin_tildes.lower().split()
    return " ".join(sorted(tokens))


def _similitud(a: str, b: str) -> float:
    """Score 0.0–1.0 entre dos textos ya normalizados."""
    return SequenceMatcher(None, a, b).ratio()


def buscar_similares(
    db: Session, supermercado_id: int, texto: str, minimo: float | None = None
) -> list[Candidato]:
    """Alias del supermercado parecidos a `texto`, de más a menos parecido.

    Solo devuelve los que llegan a `minimo` (por defecto, el umbral de
    sugerencia). Un mismo producto aparece una sola vez, con su mejor alias.
    """
    if minimo is None:
        minimo = settings.umbral_sugerencia

    objetivo = normalizar(texto)
    if not objetivo:
        return []

    alias_lista = db.scalars(
        select(models.AliasProducto).where(
            models.AliasProducto.supermercado_id == supermercado_id
        )
    ).all()

    mejores: dict[int, Candidato] = {}
    for alias in alias_lista:
        score = _similitud(objetivo, normalizar(alias.texto_alias))
        if score < minimo:
            continue
        actual = mejores.get(alias.producto_id)
        if actual is None or score > actual.score:
            mejores[alias.producto_id] = Candidato(
                producto_id=alias.producto_id,
                texto_alias=alias.texto_alias,
                score=score,
            )

    return sorted(mejores.values(), key=lambda c: c.score, reverse=True)


def mejor_candidato_automatico(
    db: Session, supermercado_id: int, texto: str
) -> Candidato | None:
    """Candidato lo bastante bueno como para asignarlo sin preguntar.

    Devuelve `None` si el mejor no llega a `umbral_auto`, o si hay empate entre
    dos productos distintos (ambigüedad real: mejor preguntar que acertar a
    medias).
    """
    candidatos = buscar_similares(
        db, supermercado_id, texto, minimo=settings.umbral_auto
    )
    if not candidatos:
        return None
    if len(candidatos) > 1 and candidatos[1].score == candidatos[0].score:
        return None
    return candidatos[0]
