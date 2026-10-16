"""Seed PROVISORIO com poucos dados, so para testar o agente.

Troque pelo gerador de dados sinteticos definitivo. Mantenha os mesmos labels,
relacoes e propriedades de docs/graph-model.md para o agente continuar funcionando.
"""
from src.graph_client import get_graph

SERVICOS = [
    ("pagamentos", "alta"), ("checkout", "alta"), ("api-gateway", "alta"),
    ("autenticacao", "alta"), ("banco-de-dados", "alta"), ("catalogo", "media"),
    ("busca", "media"), ("notificacoes", "baixa"),
]
# (A, B) = A depende de B
DEPENDENCIAS = [
    ("checkout", "pagamentos"), ("checkout", "catalogo"), ("api-gateway", "checkout"),
    ("api-gateway", "autenticacao"), ("pagamentos", "autenticacao"),
    ("pagamentos", "banco-de-dados"), ("notificacoes", "pagamentos"),
    ("catalogo", "banco-de-dados"), ("busca", "catalogo"),
]
EQUIPES = [("Pagamentos", "pagamentos"), ("Plataforma", "banco-de-dados"),
           ("Identidade", "autenticacao"), ("Loja", "checkout")]
PESSOAS = [("Ana", "Pagamentos"), ("Bruno", "Pagamentos"), ("Carla", "Plataforma"),
           ("Diego", "Identidade"), ("Elisa", "Loja")]
INCIDENTES = [
    ("INC-1", "Timeout no gateway de pagamentos", "alta", "2026-08-02", "Pool de conexoes esgotado", "pagamentos", "Ana"),
    ("INC-2", "Falha de login em massa", "alta", "2026-08-20", "Certificado expirado", "autenticacao", "Diego"),
    ("INC-3", "Lentidao no checkout", "media", "2026-09-05", "Consulta lenta no banco", "banco-de-dados", "Carla"),
    ("INC-4", "Pagamentos duplicados", "alta", "2026-09-18", "Retry sem idempotencia", "pagamentos", "Bruno"),
    ("INC-5", "Catalogo fora do ar", "media", "2026-10-01", "Deploy com migracao quebrada", "catalogo", "Carla"),
]


def main():
    g = get_graph()
    try:
        g.delete()
    except Exception:
        pass
    g = get_graph()

    g.query("UNWIND $r AS x CREATE (:Servico {nome: x[0], criticidade: x[1]})", {"r": [list(s) for s in SERVICOS]})
    g.query("UNWIND $r AS x MATCH (a:Servico {nome: x[0]}), (b:Servico {nome: x[1]}) CREATE (a)-[:DEPENDE_DE]->(b)",
            {"r": [list(d) for d in DEPENDENCIAS]})
    g.query("UNWIND $r AS x CREATE (:Equipe {nome: x[0]})", {"r": [[e[0]] for e in EQUIPES]})
    g.query("UNWIND $r AS x MATCH (e:Equipe {nome: x[0]}), (s:Servico {nome: x[1]}) CREATE (e)-[:RESPONSAVEL_POR]->(s)",
            {"r": [list(e) for e in EQUIPES]})
    g.query("UNWIND $r AS x MATCH (e:Equipe {nome: x[1]}) CREATE (:Pessoa {nome: x[0]})-[:MEMBRO_DE]->(e)",
            {"r": [list(p) for p in PESSOAS]})
    g.query(
        """UNWIND $r AS x
           MATCH (s:Servico {nome: x[5]}), (p:Pessoa {nome: x[6]})
           CREATE (i:Incidente {id: x[0], titulo: x[1], gravidade: x[2], data: x[3], causa: x[4]})
           CREATE (i)-[:AFETOU]->(s)
           CREATE (p)-[:RESOLVEU]->(i)""",
        {"r": [list(i) for i in INCIDENTES]},
    )
    print("Seed de exemplo carregado.")


if __name__ == "__main__":
    main()
