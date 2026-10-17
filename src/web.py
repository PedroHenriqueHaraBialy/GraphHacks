"""Interface web: pergunta, resposta, subgrafo desenhado e consultas Cypher.

Uso:  python -m src.web   ->   http://127.0.0.1:5000
"""
from pathlib import Path

from flask import Flask, jsonify, request

from .agent import run_agent

STATIC = Path(__file__).resolve().parent / "static"
app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")


def juntar_subgrafos(trace):
    """Une os subgrafos de todas as ferramentas usadas numa unica visualizacao."""
    nos, arestas = {}, {}
    for passo in trace:
        sub = passo.get("subgrafo") or {}
        for n in sub.get("nodes", []):
            atual = nos.setdefault(n["id"], dict(n))
            atual["foco"] = atual.get("foco") or n.get("foco", False)
            atual["detalhe"] = atual.get("detalhe") or n.get("detalhe")
            atual["novo"] = atual.get("novo") or n.get("novo", False)
        for e in sub.get("edges", []):
            chave = (e["source"], e["target"], e["rel"])
            existente = arestas.setdefault(chave, dict(e))
            existente["novo"] = existente.get("novo") or e.get("novo", False)
    return {"nodes": list(nos.values()), "edges": list(arestas.values())}


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.post("/api/ask")
def ask():
    dados = request.get_json(silent=True) or {}
    pergunta = (dados.get("pergunta") or "").strip()
    if not pergunta:
        return jsonify(erro="Digite uma pergunta."), 400
    if len(pergunta) > 500:
        return jsonify(erro="Pergunta muito longa (maximo 500 caracteres)."), 400
    agir = bool(dados.get("agir"))  # modo acao: libera as ferramentas de escrita
    try:
        resultado = run_agent(pergunta, verbose=False, permitir_escrita=agir)
    except Exception as exc:  # mostra o motivo na tela em vez de quebrar
        return jsonify(erro=f"{type(exc).__name__}: {exc}"), 500
    return jsonify(
        answer=resultado["answer"],
        trace=resultado["trace"],
        grafo=juntar_subgrafos(resultado["trace"]),
    )


if __name__ == "__main__":
    print("Abra http://127.0.0.1:5000 no navegador")
    app.run(host="127.0.0.1", port=5000, debug=False)
