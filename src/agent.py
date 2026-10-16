"""Agente de analise de impacto de incidentes sobre um grafo no FalkorDB.

Uso:  python -m src.agent "O que quebra se o servico pagamentos cair?"
"""
import json
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

from .graph_client import get_graph
from .tools import TOOLS_SCHEMA, execute_tool

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MAX_STEPS = 8

SYSTEM = """Voce e um agente de analise de incidentes de infraestrutura.
Todo o seu conhecimento sobre servicos, dependencias, equipes, pessoas e incidentes
vem de um grafo no FalkorDB, acessado SOMENTE pelas ferramentas disponiveis.

Regras:
- Nunca invente servicos, pessoas, equipes ou incidentes. Se a ferramenta nao
  devolver algo, diga que nao ha registro no grafo.
- Se nao tiver certeza do nome de um servico, chame listar_servicos primeiro.
- Para perguntas de impacto, use analisar_impacto e explique o CAMINHO de
  dependencia ate cada servico afetado (campo 'caminho').
- Quando fizer sentido, combine ferramentas: impacto + especialistas + incidentes
  parecidos, e termine com recomendacoes objetivas (quem acionar, o que verificar).
- Responda em portugues, de forma objetiva, citando os caminhos do grafo."""


def run_agent(pergunta, verbose=True):
    client = Anthropic()  # le ANTHROPIC_API_KEY do ambiente
    graph = get_graph()
    messages = [{"role": "user", "content": pergunta}]
    trace = []

    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            tools=TOOLS_SCHEMA,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            answer = "".join(b.text for b in resp.content if b.type == "text")
            return {"answer": answer, "trace": trace}

        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            try:
                out = execute_tool(graph, block.name, block.input)
                trace.append({"ferramenta": block.name, "entrada": block.input, "consultas": out["consultas"]})
                content, is_error = json.dumps(out["resultado"], ensure_ascii=False, default=str), False
            except Exception as exc:  # devolve o erro ao modelo para ele se corrigir
                content, is_error = f"Erro ao executar a ferramenta: {exc}", True
                trace.append({"ferramenta": block.name, "entrada": block.input, "erro": str(exc)})
            if verbose:
                print(f"  -> ferramenta: {block.name} {block.input}")
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error}
            )
        messages.append({"role": "user", "content": results})

    return {"answer": "Limite de passos atingido sem resposta final.", "trace": trace}


def imprimir_trace(trace):
    print("\n=== Consultas Cypher executadas no grafo ===")
    for i, passo in enumerate(trace, 1):
        print(f"\n[{i}] {passo['ferramenta']} {passo['entrada']}")
        for c in passo.get("consultas", []):
            print(f"    Cypher: {c['cypher']}")
            print(f"    Params: {c['params']}  ->  {len(c['rows'])} linha(s)")
        if "erro" in passo:
            print(f"    ERRO: {passo['erro']}")


if __name__ == "__main__":
    pergunta = " ".join(sys.argv[1:]) or "O que quebra se o servico pagamentos cair?"
    print(f"Pergunta: {pergunta}\n")
    resultado = run_agent(pergunta)
    print("\n=== Resposta ===\n")
    print(resultado["answer"])
    imprimir_trace(resultado["trace"])
