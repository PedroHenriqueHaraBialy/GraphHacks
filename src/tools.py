"""Ferramentas do agente: cada uma e uma consulta Cypher sobre o grafo.

O LLM NAO escreve Cypher livre: ele escolhe uma ferramenta e passa parametros.
As consultas rodam parametrizadas, e cada uma e registrada para mostrar na demo
exatamente o que foi consultado no grafo.
"""
from .graph_client import run_query


def _consulta(graph, cypher, params):
    rows = run_query(graph, cypher, params)
    return {"cypher": " ".join(cypher.split()), "params": params, "rows": rows}


def listar_servicos(graph):
    c = _consulta(
        graph,
        "MATCH (s:Servico) RETURN s.nome AS servico, s.criticidade AS criticidade ORDER BY s.nome",
        {},
    )
    return {"resultado": c["rows"], "consultas": [c]}


def info_servico(graph, servico):
    c = _consulta(
        graph,
        """
        MATCH (s:Servico {nome: $servico})
        OPTIONAL MATCH (e:Equipe)-[:RESPONSAVEL_POR]->(s)
        OPTIONAL MATCH (s)-[:DEPENDE_DE]->(dep:Servico)
        RETURN s.nome AS servico, s.criticidade AS criticidade,
               collect(DISTINCT e.nome) AS equipes_responsaveis,
               collect(DISTINCT dep.nome) AS depende_diretamente_de
        """,
        {"servico": servico},
    )
    return {"resultado": c["rows"], "consultas": [c]}


def analisar_impacto(graph, servico, profundidade=4):
    n = max(1, min(int(profundidade), 6))  # inteiro limitado: vai no texto da consulta
    c = _consulta(
        graph,
        f"""
        MATCH p = (s:Servico {{nome: $servico}})<-[:DEPENDE_DE*1..{n}]-(a:Servico)
        RETURN a.nome AS afetado, a.criticidade AS criticidade,
               [x IN nodes(p) | x.nome] AS caminho, length(p) AS saltos
        ORDER BY saltos
        """,
        {"servico": servico},
    )
    vistos, afetados = set(), []
    for r in c["rows"]:
        if r["afetado"] in vistos:
            continue  # mantem so o caminho mais curto para cada servico afetado
        vistos.add(r["afetado"])
        cadeia = list(reversed(r["caminho"]))
        afetados.append(
            {
                "afetado": r["afetado"],
                "criticidade": r["criticidade"],
                "saltos": r["saltos"],
                "caminho": " depende de ".join(cadeia),
            }
        )
    return {"resultado": afetados, "consultas": [c]}


def buscar_especialistas(graph, servico):
    resolveram = _consulta(
        graph,
        """
        MATCH (p:Pessoa)-[:RESOLVEU]->(i:Incidente)-[:AFETOU]->(s:Servico {nome: $servico})
        RETURN p.nome AS pessoa, count(i) AS incidentes_resolvidos
        ORDER BY incidentes_resolvidos DESC LIMIT 5
        """,
        {"servico": servico},
    )
    equipe = _consulta(
        graph,
        """
        MATCH (p:Pessoa)-[:MEMBRO_DE]->(e:Equipe)-[:RESPONSAVEL_POR]->(s:Servico {nome: $servico})
        RETURN p.nome AS pessoa, e.nome AS equipe
        """,
        {"servico": servico},
    )
    return {
        "resultado": {
            "quem_ja_resolveu_incidentes_neste_servico": resolveram["rows"],
            "equipe_responsavel": equipe["rows"],
        },
        "consultas": [resolveram, equipe],
    }


def incidentes_parecidos(graph, servico):
    diretos = _consulta(
        graph,
        """
        MATCH (i:Incidente)-[:AFETOU]->(s:Servico {nome: $servico})
        RETURN i.titulo AS incidente, i.causa AS causa, i.data AS data,
               i.gravidade AS gravidade, s.nome AS servico_afetado
        ORDER BY data DESC LIMIT 5
        """,
        {"servico": servico},
    )
    via_dependentes = _consulta(
        graph,
        """
        MATCH (s:Servico {nome: $servico})<-[:DEPENDE_DE*1..2]-(d:Servico)<-[:AFETOU]-(i:Incidente)
        RETURN DISTINCT i.titulo AS incidente, i.causa AS causa, i.data AS data,
               i.gravidade AS gravidade, d.nome AS servico_afetado
        ORDER BY data DESC LIMIT 5
        """,
        {"servico": servico},
    )
    return {
        "resultado": {
            "no_proprio_servico": diretos["rows"],
            "em_servicos_que_dependem_dele": via_dependentes["rows"],
        },
        "consultas": [diretos, via_dependentes],
    }


_SERVICO = {
    "type": "object",
    "properties": {
        "servico": {"type": "string", "description": "Nome exato do servico (use listar_servicos se tiver duvida)."}
    },
    "required": ["servico"],
}

TOOLS_SCHEMA = [
    {
        "name": "listar_servicos",
        "description": "Lista todos os servicos do grafo, com criticidade. Use para descobrir o nome exato de um servico.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "info_servico",
        "description": "Dados de um servico: criticidade, equipes responsaveis e de quem ele depende diretamente.",
        "input_schema": _SERVICO,
    },
    {
        "name": "analisar_impacto",
        "description": "Percorre o grafo de dependencias e lista TODOS os servicos afetados se o servico informado cair, com o caminho de dependencia ate cada um.",
        "input_schema": {
            "type": "object",
            "properties": {
                "servico": {"type": "string", "description": "Nome exato do servico que caiu."},
                "profundidade": {"type": "integer", "description": "Niveis de dependencia a percorrer (1 a 6). Padrao 4."},
            },
            "required": ["servico"],
        },
    },
    {
        "name": "buscar_especialistas",
        "description": "Quem ja resolveu incidentes no servico e quais pessoas compoem a equipe responsavel por ele.",
        "input_schema": _SERVICO,
    },
    {
        "name": "incidentes_parecidos",
        "description": "Incidentes passados no proprio servico e em servicos que dependem dele, com causa e data.",
        "input_schema": _SERVICO,
    },
]

_IMPL = {
    "listar_servicos": lambda g, a: listar_servicos(g),
    "info_servico": lambda g, a: info_servico(g, a["servico"]),
    "analisar_impacto": lambda g, a: analisar_impacto(g, a["servico"], a.get("profundidade", 4)),
    "buscar_especialistas": lambda g, a: buscar_especialistas(g, a["servico"]),
    "incidentes_parecidos": lambda g, a: incidentes_parecidos(g, a["servico"]),
}


def execute_tool(graph, name, args):
    if name not in _IMPL:
        raise ValueError(f"Ferramenta desconhecida: {name}")
    return _IMPL[name](graph, args or {})
