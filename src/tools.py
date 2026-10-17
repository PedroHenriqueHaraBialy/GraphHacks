"""Ferramentas do agente: cada uma e uma consulta Cypher sobre o grafo.

O LLM NAO escreve Cypher livre: ele escolhe uma ferramenta e passa parametros.
As consultas rodam parametrizadas, e cada uma e registrada para mostrar na demo
exatamente o que foi consultado no grafo. Cada ferramenta tambem devolve o
"subgrafo" (nos e arestas) que percorreu, para a interface desenhar o caminho.
"""
from datetime import datetime

from .graph_client import run_query


def _consulta(graph, cypher, params, escrita=False):
    rows = run_query(graph, cypher, params)
    return {"cypher": " ".join(cypher.split()), "params": params, "rows": rows, "escrita": escrita}


# ---- subgrafo (para visualizacao) -------------------------------------------

def _novo_sub():
    return {"nodes": {}, "edges": {}}


def _no(sub, kind, nome, foco=False, detalhe=None, novo=False):
    nid = f"{kind}:{nome}"
    n = sub["nodes"].setdefault(
        nid, {"id": nid, "label": nome, "kind": kind, "foco": False, "detalhe": None, "novo": False}
    )
    n["foco"] = n["foco"] or foco
    n["novo"] = n["novo"] or novo
    if detalhe:
        n["detalhe"] = detalhe
    return nid


def _aresta(sub, origem, destino, rel, rotulo=None, novo=False):
    sub["edges"][(origem, destino, rel)] = {
        "source": origem, "target": destino, "rel": rel, "label": rotulo or rel, "novo": novo,
    }


def _fim(sub):
    return {"nodes": list(sub["nodes"].values()), "edges": list(sub["edges"].values())}


# ---- ferramentas -------------------------------------------------------------

def listar_servicos(graph):
    c = _consulta(
        graph,
        "MATCH (s:Servico) RETURN s.nome AS servico, s.criticidade AS criticidade ORDER BY s.nome",
        {},
    )
    return {"resultado": c["rows"], "consultas": [c], "subgrafo": _fim(_novo_sub())}


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
    sub = _novo_sub()
    for r in c["rows"]:
        if not r.get("servico"):
            continue
        sv = _no(sub, "servico", r["servico"], foco=True, detalhe=f"criticidade {r['criticidade']}")
        for nome in r["equipes_responsaveis"] or []:
            _aresta(sub, _no(sub, "equipe", nome), sv, "RESPONSAVEL_POR")
        for nome in r["depende_diretamente_de"] or []:
            _aresta(sub, sv, _no(sub, "servico", nome), "DEPENDE_DE")
    return {"resultado": c["rows"], "consultas": [c], "subgrafo": _fim(sub)}


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
    vistos, afetados, sub = set(), [], _novo_sub()
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
        ids = [
            _no(sub, "servico", nome, foco=(nome == servico),
                detalhe=f"criticidade {r['criticidade']}" if nome == r["afetado"] else None)
            for nome in r["caminho"]
        ]
        for pai, filho in zip(ids[:-1], ids[1:]):
            _aresta(sub, filho, pai, "DEPENDE_DE")  # o filho depende do pai
    return {"resultado": afetados, "consultas": [c], "subgrafo": _fim(sub)}


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
    sub = _novo_sub()
    if resolveram["rows"] or equipe["rows"]:
        sv = _no(sub, "servico", servico, foco=True)
        for r in resolveram["rows"]:
            q = r["incidentes_resolvidos"]
            p = _no(sub, "pessoa", r["pessoa"], detalhe=f"{q} incidente(s) resolvido(s) neste servico")
            _aresta(sub, p, sv, "RESOLVEU", f"RESOLVEU ({q})")
        for r in equipe["rows"]:
            p = _no(sub, "pessoa", r["pessoa"])
            e = _no(sub, "equipe", r["equipe"])
            _aresta(sub, p, e, "MEMBRO_DE")
            _aresta(sub, e, sv, "RESPONSAVEL_POR")
    return {
        "resultado": {
            "quem_ja_resolveu_incidentes_neste_servico": resolveram["rows"],
            "equipe_responsavel": equipe["rows"],
        },
        "consultas": [resolveram, equipe],
        "subgrafo": _fim(sub),
    }


def incidentes_parecidos(graph, servico):
    diretos = _consulta(
        graph,
        """
        MATCH (i:Incidente)-[:AFETOU]->(s:Servico {nome: $servico})
        OPTIONAL MATCH (i)-[:ATRIBUIDO_A]->(r:Pessoa)
        RETURN i.id AS id, i.titulo AS incidente, i.causa AS causa, i.data AS data,
               i.gravidade AS gravidade, s.nome AS servico_afetado,
               collect(DISTINCT r.nome) AS atribuido_a
        ORDER BY data DESC LIMIT 5
        """,
        {"servico": servico},
    )
    via_dependentes = _consulta(
        graph,
        """
        MATCH (s:Servico {nome: $servico})<-[:DEPENDE_DE*1..2]-(d:Servico)<-[:AFETOU]-(i:Incidente)
        OPTIONAL MATCH (i)-[:ATRIBUIDO_A]->(r:Pessoa)
        RETURN i.id AS id, i.titulo AS incidente, i.causa AS causa, i.data AS data,
               i.gravidade AS gravidade, d.nome AS servico_afetado,
               collect(DISTINCT r.nome) AS atribuido_a
        ORDER BY data DESC LIMIT 5
        """,
        {"servico": servico},
    )
    sub = _novo_sub()
    if diretos["rows"] or via_dependentes["rows"]:
        sv = _no(sub, "servico", servico, foco=True)
        for r in diretos["rows"]:
            i = _no(sub, "incidente", r["incidente"], detalhe=f"{r['id']}: {r['causa']} ({r['data']})")
            _aresta(sub, i, sv, "AFETOU")
            for nome in r.get("atribuido_a") or []:
                _aresta(sub, i, _no(sub, "pessoa", nome), "ATRIBUIDO_A")
        for r in via_dependentes["rows"]:
            i = _no(sub, "incidente", r["incidente"], detalhe=f"{r['id']}: {r['causa']} ({r['data']})")
            d = _no(sub, "servico", r["servico_afetado"])
            _aresta(sub, i, d, "AFETOU")
            _aresta(sub, d, sv, "DEPENDE_DE", "DEPENDE_DE (1 a 2 niveis)")
            for nome in r.get("atribuido_a") or []:
                _aresta(sub, i, _no(sub, "pessoa", nome), "ATRIBUIDO_A")
    return {
        "resultado": {
            "no_proprio_servico": diretos["rows"],
            "em_servicos_que_dependem_dele": via_dependentes["rows"],
        },
        "consultas": [diretos, via_dependentes],
        "subgrafo": _fim(sub),
    }


# ---- ferramentas de ESCRITA (so disponiveis no "modo acao") ------------------

GRAVIDADES = {"baixa", "media", "alta"}


def _erro(msg, consultas=None):
    return {"resultado": {"erro": msg}, "consultas": consultas or [], "subgrafo": _fim(_novo_sub())}


def registrar_incidente(graph, servico, titulo, gravidade="media", causa=None):
    titulo = (titulo or "").strip()
    if not titulo or len(titulo) > 120:
        return _erro("Titulo obrigatorio, com no maximo 120 caracteres.")
    gravidade = (gravidade or "media").strip().lower().replace("\u00e9", "e")
    if gravidade not in GRAVIDADES:
        return _erro("Gravidade invalida. Use: baixa, media ou alta.")
    causa = (causa or "em investigacao").strip()[:200]

    consultas = []
    existe = _consulta(
        graph, "MATCH (s:Servico {nome: $servico}) RETURN s.nome AS servico", {"servico": servico}
    )
    consultas.append(existe)
    if not existe["rows"]:
        return _erro(f"Servico '{servico}' nao existe no grafo. Nada foi gravado.", consultas)

    duplicado = _consulta(
        graph,
        """
        MATCH (i:Incidente {titulo: $titulo})-[:AFETOU]->(s:Servico {nome: $servico})
        RETURN i.id AS id, i.titulo AS titulo
        """,
        {"titulo": titulo, "servico": servico},
    )
    consultas.append(duplicado)
    sub = _novo_sub()
    sv = _no(sub, "servico", servico, foco=True)
    if duplicado["rows"]:
        inc = duplicado["rows"][0]
        _aresta(sub, _no(sub, "incidente", inc["titulo"], detalhe=inc["id"]), sv, "AFETOU")
        return {
            "resultado": {"criado": False, "motivo": "Incidente igual ja registrado.", "id": inc["id"]},
            "consultas": consultas,
            "subgrafo": _fim(sub),
        }

    agora = datetime.now()
    novo_id = "INC-" + agora.strftime("%m%d-%H%M%S")
    params = {
        "servico": servico, "id": novo_id, "titulo": titulo, "gravidade": gravidade,
        "causa": causa, "data": agora.date().isoformat(),
    }
    criacao = _consulta(
        graph,
        """
        MATCH (s:Servico {nome: $servico})
        CREATE (i:Incidente {id: $id, titulo: $titulo, gravidade: $gravidade, data: $data,
                             causa: $causa, status: 'aberto', origem: 'agente'})
        CREATE (i)-[:AFETOU]->(s)
        RETURN i.id AS id
        """,
        params,
        escrita=True,
    )
    consultas.append(criacao)
    i = _no(sub, "incidente", titulo, detalhe=f"{novo_id}: {causa} ({params['data']})", novo=True)
    _aresta(sub, i, sv, "AFETOU", novo=True)
    return {
        "resultado": {
            "criado": True, "id": novo_id, "servico": servico, "titulo": titulo,
            "gravidade": gravidade, "causa": causa, "data": params["data"], "status": "aberto",
        },
        "consultas": consultas,
        "subgrafo": _fim(sub),
    }


def atribuir_responsavel(graph, incidente_id, pessoa):
    consultas = []
    inc = _consulta(
        graph,
        """
        MATCH (i:Incidente {id: $id})-[:AFETOU]->(s:Servico)
        RETURN i.titulo AS titulo, s.nome AS servico
        """,
        {"id": incidente_id},
    )
    consultas.append(inc)
    if not inc["rows"]:
        return _erro(f"Incidente '{incidente_id}' nao encontrado. Nada foi gravado.", consultas)
    p = _consulta(
        graph, "MATCH (p:Pessoa {nome: $pessoa}) RETURN p.nome AS pessoa", {"pessoa": pessoa}
    )
    consultas.append(p)
    if not p["rows"]:
        return _erro(f"Pessoa '{pessoa}' nao existe no grafo. Nada foi gravado.", consultas)

    ligacao = _consulta(
        graph,
        """
        MATCH (i:Incidente {id: $id}), (p:Pessoa {nome: $pessoa})
        MERGE (i)-[:ATRIBUIDO_A]->(p)
        RETURN i.id AS id, p.nome AS pessoa
        """,
        {"id": incidente_id, "pessoa": pessoa},
        escrita=True,
    )
    consultas.append(ligacao)
    titulo, servico = inc["rows"][0]["titulo"], inc["rows"][0]["servico"]
    sub = _novo_sub()
    sv = _no(sub, "servico", servico, foco=True)
    i = _no(sub, "incidente", titulo, detalhe=incidente_id)
    pe = _no(sub, "pessoa", pessoa)
    _aresta(sub, i, sv, "AFETOU")
    _aresta(sub, i, pe, "ATRIBUIDO_A", novo=True)
    return {
        "resultado": {"atribuido": True, "incidente": incidente_id, "titulo": titulo, "pessoa": pessoa},
        "consultas": consultas,
        "subgrafo": _fim(sub),
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
        "description": "Incidentes passados no proprio servico e em servicos que dependem dele, com id, causa, data e quem esta atribuido (atribuido_a).",
        "input_schema": _SERVICO,
    },
]

TOOLS_ESCRITA = [
    {
        "name": "registrar_incidente",
        "description": "ESCRITA: grava um NOVO incidente no grafo, ligado ao servico afetado. Use SOMENTE quando o usuario pedir explicitamente para registrar/abrir um incidente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "servico": {"type": "string", "description": "Nome exato do servico afetado."},
                "titulo": {"type": "string", "description": "Titulo curto do incidente (ate 120 caracteres)."},
                "gravidade": {"type": "string", "enum": ["baixa", "media", "alta"]},
                "causa": {"type": "string", "description": "Causa provavel, se o usuario informou."},
            },
            "required": ["servico", "titulo"],
        },
    },
    {
        "name": "atribuir_responsavel",
        "description": "ESCRITA: atribui um incidente existente a uma pessoa que EXISTE no grafo. Use SOMENTE quando o usuario pedir explicitamente para atribuir/acionar alguem. Use o id do incidente (ex.: INC-1) e um nome devolvido pelas outras ferramentas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incidente_id": {"type": "string", "description": "Id do incidente, como INC-1."},
                "pessoa": {"type": "string", "description": "Nome exato da pessoa."},
            },
            "required": ["incidente_id", "pessoa"],
        },
    },
]

NOMES_ESCRITA = {t["name"] for t in TOOLS_ESCRITA}

_IMPL = {
    "listar_servicos": lambda g, a: listar_servicos(g),
    "info_servico": lambda g, a: info_servico(g, a["servico"]),
    "analisar_impacto": lambda g, a: analisar_impacto(g, a["servico"], a.get("profundidade", 4)),
    "buscar_especialistas": lambda g, a: buscar_especialistas(g, a["servico"]),
    "incidentes_parecidos": lambda g, a: incidentes_parecidos(g, a["servico"]),
    "registrar_incidente": lambda g, a: registrar_incidente(
        g, a["servico"], a["titulo"], a.get("gravidade", "media"), a.get("causa")
    ),
    "atribuir_responsavel": lambda g, a: atribuir_responsavel(g, a["incidente_id"], a["pessoa"]),
}


def execute_tool(graph, name, args, permitir_escrita=False):
    if name not in _IMPL:
        raise ValueError(f"Ferramenta desconhecida: {name}")
    if name in NOMES_ESCRITA and not permitir_escrita:
        raise PermissionError("Ferramenta de escrita desativada: o modo acao esta desligado.")
    return _IMPL[name](graph, args or {})
