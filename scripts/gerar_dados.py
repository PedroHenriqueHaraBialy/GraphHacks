"""Gerador de dados SINTETICOS para o grafo de incidentes.

Cria ~42 servicos em camadas, 9 equipes, 27 pessoas e ~260 incidentes com
historico de 12 meses. E deterministico: rodar duas vezes gera os mesmos dados.
Respeita o modelo de docs/graph-model.md.

Uso:  python -m scripts.gerar_dados     (APAGA e recria o grafo)
"""
import random
from datetime import date, timedelta

# (nome, criticidade, equipe responsavel)
SERVICOS = [
    # infraestrutura e dados
    ("banco-de-dados", "alta", "Plataforma"),
    ("banco-de-dados-pedidos", "alta", "Plataforma"),
    ("banco-de-dados-catalogo", "media", "Plataforma"),
    ("cache-redis", "alta", "Plataforma"),
    ("fila-mensagens", "alta", "Plataforma"),
    ("armazenamento-arquivos", "media", "Plataforma"),
    ("observabilidade", "media", "Plataforma"),
    # identidade
    ("autenticacao", "alta", "Identidade"),
    ("autorizacao", "alta", "Identidade"),
    ("gestao-de-usuarios", "media", "Identidade"),
    ("perfil-usuario", "baixa", "Identidade"),
    # comunicacao
    ("email", "baixa", "Comunicacao"),
    ("sms", "baixa", "Comunicacao"),
    ("push", "baixa", "Comunicacao"),
    ("notificacoes", "media", "Comunicacao"),
    # pagamentos
    ("antifraude", "alta", "Pagamentos"),
    ("cartoes", "alta", "Pagamentos"),
    ("pix", "alta", "Pagamentos"),
    ("pagamentos", "alta", "Pagamentos"),
    ("conciliacao", "media", "Pagamentos"),
    ("faturamento", "media", "Pagamentos"),
    # catalogo
    ("precos", "media", "Catalogo"),
    ("catalogo", "alta", "Catalogo"),
    ("busca", "media", "Catalogo"),
    ("avaliacoes", "baixa", "Catalogo"),
    ("recomendacoes", "baixa", "Catalogo"),
    ("promocoes", "media", "Catalogo"),
    ("cupons", "baixa", "Catalogo"),
    # logistica
    ("estoque", "alta", "Logistica"),
    ("frete", "media", "Logistica"),
    ("entregas", "media", "Logistica"),
    ("rastreamento", "baixa", "Logistica"),
    # loja
    ("carrinho", "alta", "Loja"),
    ("pedidos", "alta", "Loja"),
    ("checkout", "alta", "Loja"),
    # dados e analise
    ("data-warehouse", "baixa", "Dados"),
    ("analytics", "baixa", "Dados"),
    ("relatorios", "baixa", "Dados"),
    # experiencia (borda)
    ("api-gateway", "alta", "Experiencia"),
    ("app-mobile-bff", "alta", "Experiencia"),
    ("web-frontend", "alta", "Experiencia"),
    ("cdn", "media", "Experiencia"),
]

# servico -> servicos dos quais ele depende (A depende de B)
DEPENDENCIAS = {
    "autenticacao": ["banco-de-dados", "cache-redis"],
    "autorizacao": ["autenticacao", "banco-de-dados"],
    "gestao-de-usuarios": ["banco-de-dados", "autenticacao"],
    "perfil-usuario": ["gestao-de-usuarios", "cache-redis"],
    "email": ["fila-mensagens"],
    "sms": ["fila-mensagens"],
    "push": ["fila-mensagens"],
    "notificacoes": ["email", "sms", "push", "fila-mensagens"],
    "antifraude": ["banco-de-dados", "cache-redis"],
    "cartoes": ["banco-de-dados", "autenticacao"],
    "pix": ["banco-de-dados", "fila-mensagens"],
    "pagamentos": ["autenticacao", "banco-de-dados", "antifraude", "cartoes", "pix", "fila-mensagens"],
    "conciliacao": ["pagamentos", "banco-de-dados"],
    "faturamento": ["pagamentos", "banco-de-dados-pedidos"],
    "precos": ["banco-de-dados-catalogo", "cache-redis"],
    "catalogo": ["banco-de-dados-catalogo", "cache-redis", "armazenamento-arquivos", "precos"],
    "busca": ["catalogo", "cache-redis"],
    "avaliacoes": ["banco-de-dados-catalogo", "gestao-de-usuarios"],
    "recomendacoes": ["catalogo", "perfil-usuario", "cache-redis"],
    "promocoes": ["precos", "banco-de-dados-catalogo"],
    "cupons": ["promocoes", "banco-de-dados"],
    "estoque": ["banco-de-dados-pedidos", "fila-mensagens"],
    "frete": ["estoque", "cache-redis"],
    "entregas": ["estoque", "banco-de-dados-pedidos", "fila-mensagens"],
    "rastreamento": ["entregas", "notificacoes"],
    "carrinho": ["catalogo", "precos", "cache-redis", "promocoes", "cupons"],
    "pedidos": ["banco-de-dados-pedidos", "estoque", "fila-mensagens", "notificacoes"],
    "checkout": ["carrinho", "pagamentos", "pedidos", "frete", "autenticacao"],
    "data-warehouse": ["banco-de-dados", "banco-de-dados-pedidos", "fila-mensagens"],
    "analytics": ["data-warehouse"],
    "relatorios": ["data-warehouse", "autorizacao"],
    "api-gateway": ["autenticacao", "autorizacao", "checkout", "catalogo", "busca", "pedidos",
                    "perfil-usuario", "rastreamento", "cache-redis"],
    "app-mobile-bff": ["api-gateway", "push", "observabilidade"],
    "web-frontend": ["api-gateway", "cdn", "recomendacoes", "avaliacoes"],
    "cdn": ["armazenamento-arquivos"],
}

# equipe -> pessoas (a ordem define quem e "especialista": o primeiro resolve mais)
EQUIPES = {
    "Plataforma": ["Rafael Moreira", "Camila Duarte", "Thiago Nogueira"],
    "Identidade": ["Beatriz Almeida", "Lucas Ferraz", "Marina Teixeira"],
    "Comunicacao": ["Gustavo Pinto", "Larissa Campos", "Felipe Barros"],
    "Pagamentos": ["Ana Souza", "Bruno Lima", "Juliana Rocha"],
    "Catalogo": ["Diego Martins", "Patricia Gomes", "Vinicius Araujo"],
    "Logistica": ["Renata Cardoso", "Eduardo Freitas", "Aline Monteiro"],
    "Loja": ["Carlos Ribeiro", "Fernanda Dias", "Henrique Salles"],
    "Dados": ["Sofia Mendes", "Leonardo Castro", "Isabela Correia"],
    "Experiencia": ["Mateus Barbosa", "Natalia Pires", "Ricardo Azevedo"],
}

TITULOS = [
    "Lentidao em {s}", "Falha intermitente em {s}", "{s} fora do ar",
    "Erros 5xx em {s}", "Timeout em {s}", "Degradacao de desempenho em {s}",
]
CAUSAS_INFRA = [
    "Disco cheio", "Conexoes esgotadas", "Failover lento", "Manutencao sem janela",
    "Memoria insuficiente", "Replicacao atrasada", "Certificado expirado",
]
CAUSAS_APP = [
    "Pool de conexoes esgotado", "Deploy com migracao quebrada", "Retry sem idempotencia",
    "Consulta lenta no banco", "Vazamento de memoria", "Timeout em dependencia",
    "Certificado expirado", "Configuracao incorreta", "Cache invalidado em massa",
    "Pico de trafego acima do previsto",
]
CAUSAS_BORDA = [
    "Limite de requisicoes mal configurado", "Deploy com regressao", "Cache invalido",
    "DNS incorreto", "Certificado expirado", "Pico de trafego acima do previsto",
]
INFRA = {"banco-de-dados", "banco-de-dados-pedidos", "banco-de-dados-catalogo", "cache-redis",
         "fila-mensagens", "armazenamento-arquivos", "observabilidade"}
BORDA = {"api-gateway", "app-mobile-bff", "web-frontend", "cdn"}
PESO_CRIT = {"alta": 3, "media": 2, "baixa": 1}
GRAV_POR_CRIT = {
    "alta": (["alta", "media", "baixa"], [60, 30, 10]),
    "media": (["alta", "media", "baixa"], [25, 50, 25]),
    "baixa": (["alta", "media", "baixa"], [10, 40, 50]),
}
HOJE = date(2026, 10, 16)  # ancora fixa: mantem a geracao deterministica


def gerar(n_incidentes=260, semente=42):
    rng = random.Random(semente)
    nomes = [s[0] for s in SERVICOS]
    crit = {s[0]: s[1] for s in SERVICOS}
    dono = {s[0]: s[2] for s in SERVICOS}

    # consistencia basica (falha cedo se alguem editar as listas e errar)
    assert len(set(nomes)) == len(nomes), "servico duplicado"
    for a, bs in DEPENDENCIAS.items():
        assert a in crit and all(b in crit for b in bs), f"dependencia invalida em {a}"
    visitando, ok = set(), set()

    def visita(n):
        assert n not in visitando, f"ciclo de dependencia em {n}"
        if n in ok:
            return
        visitando.add(n)
        for b in DEPENDENCIAS.get(n, []):
            visita(b)
        visitando.discard(n)
        ok.add(n)

    for n in nomes:
        visita(n)

    dependentes = {n: 0 for n in nomes}
    for bs in DEPENDENCIAS.values():
        for b in bs:
            dependentes[b] += 1
    pesos = [PESO_CRIT[crit[n]] * (1 + dependentes[n] / 6) for n in nomes]

    pessoas = [(p, eq) for eq, ps in EQUIPES.items() for p in ps]
    todas = [p for p, _ in pessoas]
    pesos_equipe = [3, 2, 1]

    incidentes = []
    for k in range(1, n_incidentes + 1):
        s = rng.choices(nomes, weights=pesos)[0]
        causas = CAUSAS_INFRA if s in INFRA else CAUSAS_BORDA if s in BORDA else CAUSAS_APP
        grav = rng.choices(*GRAV_POR_CRIT[crit[s]])[0]
        if rng.random() < 0.8:
            resolvedor = rng.choices(EQUIPES[dono[s]], weights=pesos_equipe)[0]
        else:
            resolvedor = rng.choice(todas)  # ajuda de outra equipe
        data = (HOJE - timedelta(days=rng.randint(0, 364))).isoformat()
        titulo = rng.choice(TITULOS).format(s=s)
        incidentes.append((f"INC-{k:04d}", titulo, grav, data, rng.choice(causas), s, resolvedor))
    incidentes.sort(key=lambda i: i[3])
    # ids na ordem cronologica
    incidentes = [(f"INC-{k:04d}",) + i[1:] for k, i in enumerate(incidentes, 1)]

    return {
        "servicos": [(n, c) for n, c, _ in SERVICOS],
        "dependencias": [(a, b) for a, bs in DEPENDENCIAS.items() for b in bs],
        "equipes": [(eq, s) for s, _, eq in SERVICOS],  # (equipe, servico)
        "equipes_nomes": list(EQUIPES),
        "pessoas": pessoas,
        "incidentes": incidentes,
    }


def carregar(dados):
    from src.graph_client import get_graph

    g = get_graph()
    try:
        g.delete()
    except Exception:
        pass
    g = get_graph()

    g.query("UNWIND $r AS x CREATE (:Servico {nome: x[0], criticidade: x[1]})",
            {"r": [list(s) for s in dados["servicos"]]})
    g.query("UNWIND $r AS x MATCH (a:Servico {nome: x[0]}), (b:Servico {nome: x[1]}) "
            "CREATE (a)-[:DEPENDE_DE]->(b)", {"r": [list(d) for d in dados["dependencias"]]})
    g.query("UNWIND $r AS x CREATE (:Equipe {nome: x})", {"r": dados["equipes_nomes"]})
    g.query("UNWIND $r AS x MATCH (e:Equipe {nome: x[0]}), (s:Servico {nome: x[1]}) "
            "CREATE (e)-[:RESPONSAVEL_POR]->(s)", {"r": [list(e) for e in dados["equipes"]]})
    g.query("UNWIND $r AS x MATCH (e:Equipe {nome: x[1]}) "
            "CREATE (:Pessoa {nome: x[0]})-[:MEMBRO_DE]->(e)", {"r": [list(p) for p in dados["pessoas"]]})
    g.query(
        """UNWIND $r AS x
           MATCH (s:Servico {nome: x[5]}), (p:Pessoa {nome: x[6]})
           CREATE (i:Incidente {id: x[0], titulo: x[1], gravidade: x[2], data: x[3], causa: x[4],
                                status: 'resolvido', origem: 'sintetico'})
           CREATE (i)-[:AFETOU]->(s)
           CREATE (p)-[:RESOLVEU]->(i)""",
        {"r": [list(i) for i in dados["incidentes"]]},
    )


if __name__ == "__main__":
    d = gerar()
    carregar(d)
    print(
        f"Grafo carregado: {len(d['servicos'])} servicos, {len(d['dependencias'])} dependencias, "
        f"{len(d['equipes_nomes'])} equipes, {len(d['pessoas'])} pessoas, {len(d['incidentes'])} incidentes."
    )
