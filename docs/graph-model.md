# Modelo do grafo

> Mantenha este arquivo atualizado: o regulamento exige o modelo no README.

## Nos (labels) e propriedades

| Label       | Propriedades                                                              |
|-------------|---------------------------------------------------------------------------|
| `Servico`   | `nome`, `criticidade`                                                     |
| `Equipe`    | `nome`                                                                    |
| `Pessoa`    | `nome`                                                                    |
| `Incidente` | `id`, `titulo`, `gravidade`, `data`, `causa` (+ `status` e `origem`: `sintetico` nos dados gerados, `agente` quando criado pelo agente) |

## Relacoes

```
(:Servico)-[:DEPENDE_DE]->(:Servico)
(:Equipe)-[:RESPONSAVEL_POR]->(:Servico)
(:Pessoa)-[:MEMBRO_DE]->(:Equipe)
(:Incidente)-[:AFETOU]->(:Servico)
(:Pessoa)-[:RESOLVEU]->(:Incidente)
(:Incidente)-[:ATRIBUIDO_A]->(:Pessoa)     <- criada pelo agente (modo acao)
```

## Consultas de leitura (ferramentas do agente)

**O que quebra se um servico cair? (ate N niveis, N entre 1 e 6)**

```cypher
MATCH p = (s:Servico {nome: $servico})<-[:DEPENDE_DE*1..N]-(a:Servico)
RETURN a.nome AS afetado, a.criticidade AS criticidade,
       [x IN nodes(p) | x.nome] AS caminho, length(p) AS saltos
ORDER BY saltos
```

**Quem ja resolveu incidentes nesse servico?**

```cypher
MATCH (p:Pessoa)-[:RESOLVEU]->(i:Incidente)-[:AFETOU]->(s:Servico {nome: $servico})
RETURN p.nome AS pessoa, count(i) AS incidentes_resolvidos
ORDER BY incidentes_resolvidos DESC LIMIT 5
```

**Incidentes parecidos (no servico e nos que dependem dele)**

```cypher
MATCH (s:Servico {nome: $servico})<-[:DEPENDE_DE*1..2]-(d:Servico)<-[:AFETOU]-(i:Incidente)
RETURN DISTINCT i.id AS id, i.titulo AS incidente, i.causa AS causa, i.data AS data
ORDER BY data DESC LIMIT 5
```

## Consultas de escrita (somente com o "modo acao" ligado)

**Registrar um incidente** (antes, o codigo confere se o servico existe e se o incidente ja nao foi registrado)

```cypher
MATCH (s:Servico {nome: $servico})
CREATE (i:Incidente {id: $id, titulo: $titulo, gravidade: $gravidade, data: $data,
                     causa: $causa, status: 'aberto', origem: 'agente'})
CREATE (i)-[:AFETOU]->(s)
```

**Atribuir um responsavel** (idempotente: repetir nao duplica a relacao)

```cypher
MATCH (i:Incidente {id: $id}), (p:Pessoa {nome: $pessoa})
MERGE (i)-[:ATRIBUIDO_A]->(p)
```

## Teste do regulamento (regra 3)

Se retirarmos o FalkorDB, o produto deixa de funcionar: as respostas dependem
das travessias acima, e o que o agente grava fica no grafo e aparece nas
proximas consultas (por exemplo, o incidente novo surge em "incidentes parecidos").
