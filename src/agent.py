"""Agente de analise de impacto de incidentes sobre um grafo no FalkorDB.

Uso:  python -m src.agent "O que quebra se o servico pagamentos cair?"
      python -m src.agent --agir "Registre um incidente de timeout no pagamentos"
"""
import json
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

from .graph_client import get_graph
from .tools import TOOLS_ESCRITA, TOOLS_SCHEMA, execute_tool

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MAX_STEPS = 10

SYSTEM = """Voce e um agente de analise e resposta a incidentes de infraestrutura.
Todo o seu conhecimento sobre servicos, dependencias, equipes, pessoas e incidentes
vem de um grafo no FalkorDB, acessado SOMENTE pelas ferramentas disponiveis.

Regras de consulta:
- Nunca invente servicos, pessoas, equipes ou incidentes. Se a ferramenta nao
  devolver algo, diga que nao ha registro no grafo.
- Se nao tiver certeza do nome de um servico, chame listar_servicos primeiro.
- Para perguntas de impacto, use analisar_impacto e explique o CAMINHO de
  dependencia ate cada servico afetado (campo 'caminho').
- Quando fizer sentido, combine ferramentas: impacto + especialistas + incidentes
  parecidos, e termine com recomendacoes objetivas (quem acionar, o que verificar).

Regras de acao (escrita no grafo):
- Voce so grava no grafo quando o usuario PEDIR explicitamente (registrar um
  incidente, atribuir/acionar alguem). Perguntas e analises nunca gravam nada.
- Antes de atribuir, descubra quem pode ser acionado com buscar_especialistas e
  atribua apenas pessoas que existem no grafo. Use o id devolvido ao registrar.
- Se uma ferramenta de escrita devolver erro, relate o erro; nao tente contornar.
- Depois de gravar, confirme exatamente o que foi registrado (id, servico, pessoa).
- Se o usuario pedir para registrar ou atribuir e voce nao tiver essas ferramentas,
  explique que o "modo acao" esta desligado e que ele precisa ativa-lo.

Responda em portugues, de forma objetiva, citando os caminhos do grafo."""


def run_agent(pergunta, verbose=True, permitir_escrita=False):
    client = Anthropic()  # le ANTHROPIC_API_KEY do ambiente
    graph = get_graph()
    tools = TOOLS_SCHEMA + (TOOLS_ESCRITA if permitir_escrita else [])
    messages = [{"role": "user", "content": pergunta}]
    trace = []

    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            tools=tools,
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
                out = execute_tool(graph, block.name, block.input, permitir_escrita)
                trace.append(
                    {
                        "ferramenta": block.name,
                        "entrada": block.input,
                        "consultas": out["consultas"],
                        "subgrafo": out.get("subgrafo"),
                    }
                )
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
            marca = "  [ESCRITA]" if c.get("escrita") else ""
            print(f"    Cypher:{marca} {c['cypher']}")
            print(f"    Params: {c['params']}  ->  {len(c['rows'])} linha(s)")
        if "erro" in passo:
            print(f"    ERRO: {passo['erro']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    agir = False
    if args and args[0] == "--agir":
        agir, args = True, args[1:]
    pergunta = " ".join(args) or "O que quebra se o servico pagamentos cair?"
    print(f"Pergunta: {pergunta}  (modo acao: {'LIGADO' if agir else 'desligado'})\n")
    resultado = run_agent(pergunta, permitir_escrita=agir)
    print("\n=== Resposta ===\n")
    print(resultado["answer"])
    imprimir_trace(resultado["trace"])
