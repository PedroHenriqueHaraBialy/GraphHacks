# Modelo do grafo (rascunho)

> Rascunho inicial. Ajustem conforme o projeto evoluir e mantenham este
> arquivo atualizado: o regulamento exige o modelo no README.

## Nos (labels) e propriedades

| Label       | Propriedades sugeridas                       |
|-------------|----------------------------------------------|
| `Servico`   | `nome`, `criticidade`                        |
| `Equipe`    | `nome`                                       |
| `Pessoa`    | `nome`                                       |
| `Incidente` | `id`, `titulo`, `gravidade`, `data`, `causa` |

## Relacoes

```
(:Servico)-[:DEPENDE_DE]->(:Servico)
(:Equipe)-[:RESPONSAVEL_POR]->(:Servico)
(:Pessoa)-[:MEMBRO_DE]->(:Equipe)
(:Incidente)-[:AFETOU]->(:Servico)
(:Pessoa)-[:RESOLVEU]->(:Incidente)
```

## Consultas Cypher candidatas

**O que quebra se um servico cair? (ate 4 niveis de dependencia)**

```cypher
MATCH (s:Servico {nome: $servico})<-[:DEPENDE_DE*1..4]-(afetado:Servico)
RETURN DISTINCT afetado.nome AS afetado
```

**Quem ja trabalhou nesse servico (resolveu incidentes nele)?**

```cypher
MATCH (p:Pessoa)-[:RESOLVEU]->(:Incidente)-[:AFETOU]->(s:Servico {nome: $servico})
RETURN p.nome AS pessoa, count(*) AS incidentes
ORDER BY incidentes DESC
LIMIT 5
```

**Incidentes parecidos no passado (mesmo servico ou dependentes)?**

```cypher
MATCH (s:Servico {nome: $servico})<-[:DEPENDE_DE*0..2]-(d:Servico)<-[:AFETOU]-(i:Incidente)
RETURN DISTINCT i.titulo AS incidente, i.causa AS causa, i.data AS data
ORDER BY data DESC
LIMIT 5
```

## Teste do regulamento (regra 3)

Se retirarmos o FalkorDB, o produto deve parar de funcionar: as respostas
dependem das travessias acima, e nao de texto gerado pelo LLM sozinho.
