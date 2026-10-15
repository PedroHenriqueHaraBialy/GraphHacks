# Incident Graph Agent

> Projeto para o hackathon **Graph Hacks: Context for AI Agents**
> (WeMakeDevs + FalkorDB).

**Trilha:** Agents That Act on Connected Data

## Ideia

Um agente de IA que responde perguntas como *"o que quebra se este servico
cair?"* percorrendo um grafo de servicos, dependencias, equipes e incidentes
passados no FalkorDB, e mostrando o caminho do raciocinio.

*(Descrevam aqui o que o projeto faz de fato, quando estiver pronto.)*

## Modelo de dados do grafo

Veja [docs/graph-model.md](docs/graph-model.md).

## Como rodar localmente

Requisitos: Docker, Docker Compose e Python 3.10+.

```bash
# 1. Variaveis de ambiente
cp .env.example .env

# 2. Subir o FalkorDB (Browser em http://localhost:3000)
docker-compose up -d

# 3. Dependencias Python
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 4. Testar a conexao
python scripts/check_connection.py
```

Para parar: `docker-compose stop`. Para apagar os dados tambem:
`docker-compose down -v` (cuidado).

## Estrutura

```
.
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── src/                  # codigo do projeto
├── data/                 # dados sinteticos usados no grafo
├── docs/graph-model.md   # modelo do grafo e consultas Cypher
└── scripts/check_connection.py
```

## Consultas Cypher das quais o produto depende

*(Listar aqui as consultas finais usadas pelo agente.)*

## Demo

*(Link do video de demonstracao e, se houver, do deploy.)*

## Dados

Apenas dados **sinteticos** criados para este projeto.

## Uso de IA (divulgacao exigida pelo regulamento)

*(Descrevam quais assistentes de IA foram usados e para que partes do projeto.)*

## Equipe

- *(nome 1)*
- *(nome 2)*
