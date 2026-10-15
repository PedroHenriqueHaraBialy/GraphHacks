"""Teste de conexao com o FalkorDB (apenas verificacao de ambiente)."""
import os

from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

db = FalkorDB(
    host=os.getenv("FALKORDB_HOST", "localhost"),
    port=int(os.getenv("FALKORDB_PORT", "6379")),
    password=os.getenv("FALKORDB_PASSWORD") or None,
)
graph = db.select_graph(os.getenv("GRAPH_NAME", "incidentes"))

result = graph.query("RETURN 1 AS ok")
print("Conexao OK:", result.result_set)
