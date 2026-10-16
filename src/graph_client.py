"""Conexao com o FalkorDB e helper para executar consultas Cypher."""
import os

from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()


def get_graph():
    db = FalkorDB(
        host=os.getenv("FALKORDB_HOST", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
        password=os.getenv("FALKORDB_PASSWORD") or None,
    )
    return db.select_graph(os.getenv("GRAPH_NAME", "incidentes"))


def run_query(graph, cypher, params=None):
    """Executa uma consulta Cypher parametrizada e devolve uma lista de dicts."""
    result = graph.query(cypher, params or {})
    cols = [h[1] if isinstance(h, (list, tuple)) else h for h in result.header]
    return [dict(zip(cols, row)) for row in result.result_set]
