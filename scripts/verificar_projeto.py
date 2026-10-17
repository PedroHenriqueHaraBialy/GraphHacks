"""Verifica se o projeto esta pronto para rodar e para ser entregue.

Uso:
    python -m scripts.verificar_projeto          (nao gasta creditos da API)
    python -m scripts.verificar_projeto --api    (tambem testa a chave e o saldo, 1 chamada minima)

Nao grava nada no grafo e nunca imprime a chave da API.
"""
import importlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

resultados = []  # (status, titulo, dica)


def ok(t, d=""): resultados.append(("OK", t, d))
def aviso(t, d=""): resultados.append(("AVISO", t, d))
def falha(t, d=""): resultados.append(("FALHA", t, d))


def git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20)
        return r.returncode, r.stdout.strip()
    except Exception as exc:
        return 1, str(exc)


def checar_arquivos():
    obrigatorios = [
        "docker-compose.yml", ".env", ".env.example", ".gitignore", "requirements.txt", "README.md",
        "docs/graph-model.md", "src/__init__.py", "src/graph_client.py", "src/tools.py",
        "src/agent.py", "src/web.py", "src/static/index.html", "src/static/app.js",
        "scripts/gerar_dados.py", "scripts/check_connection.py",
    ]
    faltam = [a for a in obrigatorios if not (ROOT / a).exists()]
    if faltam:
        falha("Arquivos do projeto", "Faltam: " + ", ".join(faltam))
    else:
        ok("Arquivos do projeto presentes")

    def tem(arq, trecho):
        p = ROOT / arq
        return p.exists() and trecho in p.read_text(encoding="utf-8", errors="ignore")

    versoes = {
        "ferramentas de escrita (modo acao)": tem("src/tools.py", "registrar_incidente"),
        "leitura de quem esta atribuido": tem("src/tools.py", "atribuido_a"),
        "grafo legivel (interface nova)": tem("src/static/app.js", "geometria"),
        "gerador de dados maiores": (ROOT / "scripts/gerar_dados.py").exists(),
    }
    antigos = [k for k, v in versoes.items() if not v]
    if antigos:
        falha("Versao dos arquivos", "Ainda nao aplicado: " + "; ".join(antigos))
    else:
        ok("Todas as atualizacoes aplicadas (acao, atribuicao, grafo legivel, dados)")


def checar_dependencias():
    ruins = []
    for mod in ["falkordb", "dotenv", "anthropic", "flask"]:
        try:
            importlib.import_module(mod)
        except Exception:
            ruins.append(mod)
    if ruins:
        falha("Pacotes Python", "Faltam: " + ", ".join(ruins) + "  ->  pip install -r requirements.txt")
    else:
        ok("Pacotes Python instalados")


def checar_env():
    from dotenv import dotenv_values

    vals = dotenv_values(ROOT / ".env")
    faltam = [k for k in ["FALKORDB_HOST", "FALKORDB_PORT", "FALKORDB_PASSWORD", "GRAPH_NAME", "ANTHROPIC_API_KEY"]
              if not vals.get(k)]
    if faltam:
        falha(".env", "Vazias ou ausentes: " + ", ".join(faltam) + " (salvou o arquivo com Ctrl+S?)")
    else:
        ok(".env com todas as variaveis")
    chave = vals.get("ANTHROPIC_API_KEY") or ""
    if chave and not chave.startswith("sk-ant-"):
        falha("Chave da Anthropic", "Nao parece uma chave valida (deve comecar com sk-ant-).")
    elif chave:
        ok("Chave da Anthropic no formato esperado")
    for k, v in vals.items():
        if v and (v.startswith(("'", '"')) or v != v.strip()):
            aviso(".env", f"{k} tem aspas ou espacos sobrando.")


def checar_git():
    cod, saida = git("rev-parse", "--is-inside-work-tree")
    if cod != 0:
        aviso("Git", "Esta pasta nao e um repositorio git.")
        return
    _, rastreados = git("ls-files", ".env")
    if rastreados:
        falha("SEGURANCA", ".env esta no git! Rode: git rm --cached .env  e revogue a chave no console.")
    else:
        cod_i, _ = git("check-ignore", ".env")
        (ok if cod_i == 0 else falha)(".env fora do git (protegido pelo .gitignore)",
                                       "" if cod_i == 0 else "Adicione .env ao .gitignore.")
    _, pend = git("status", "--porcelain")
    if pend:
        aviso("Alteracoes sem commit", f"{len(pend.splitlines())} arquivo(s). Rode: git add . ; git commit ; git push")
    else:
        ok("Sem alteracoes pendentes")
    cod_u, nao_enviados = git("log", "@{u}..HEAD", "--oneline")
    if cod_u == 0 and nao_enviados:
        aviso("Commits nao enviados", f"{len(nao_enviados.splitlines())} commit(s) local(is). Rode: git push")
    elif cod_u == 0:
        ok("Tudo enviado ao GitHub")


def checar_readme():
    p = ROOT / "README.md"
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8", errors="ignore")
    pendentes = [m for m in ["(Descrevam", "(Listar", "(Link do video", "(descrevam", "(nome 1)"] if m in t]
    if pendentes:
        aviso("README ainda com campos para preencher", "Entrega exige: modelo do grafo, consultas, setup, video, uso de IA.")
    else:
        ok("README sem campos pendentes")


def checar_banco():
    try:
        from src.graph_client import get_graph, run_query
        g = get_graph()
        g.query("RETURN 1")
    except Exception as exc:
        falha("FalkorDB", f"Nao conectou ({type(exc).__name__}). Docker Desktop aberto? docker compose up -d")
        return None
    ok("Conexao com o FalkorDB")
    cont = {}
    for rotulo in ["Servico", "Equipe", "Pessoa", "Incidente"]:
        linhas = run_query(g, f"MATCH (n:{rotulo}) RETURN count(n) AS total", {})
        cont[rotulo] = linhas[0]["total"] if linhas else 0
    resumo = ", ".join(f"{v} {k}" for k, v in cont.items())
    if cont["Servico"] == 0:
        falha("Dados no grafo", "Grafo vazio. Rode: python -m scripts.gerar_dados")
    elif cont["Servico"] < 20 or cont["Incidente"] < 100:
        aviso("Dados no grafo", f"{resumo}. Parece o seed pequeno; para a demo rode: python -m scripts.gerar_dados")
    else:
        ok(f"Dados no grafo ({resumo})")
    return g


def checar_ferramentas(g):
    from src.graph_client import run_query
    from src.tools import execute_tool

    nomes = [r["nome"] for r in run_query(g, "MATCH (s:Servico) RETURN s.nome AS nome ORDER BY nome", {})]
    if not nomes:
        return
    alvo = "pagamentos" if "pagamentos" in nomes else nomes[0]
    for ferramenta, args in [
        ("listar_servicos", {}), ("info_servico", {"servico": alvo}),
        ("analisar_impacto", {"servico": alvo}), ("buscar_especialistas", {"servico": alvo}),
        ("incidentes_parecidos", {"servico": alvo}),
    ]:
        try:
            out = execute_tool(g, ferramenta, args)
            vazio = not out["resultado"]
            (aviso if vazio else ok)(f"Ferramenta {ferramenta}", "Rodou, mas sem resultados." if vazio else "")
        except Exception as exc:
            falha(f"Ferramenta {ferramenta}", f"{type(exc).__name__}: {str(exc)[:160]}")
    try:  # protecao: sem modo acao nada pode ser gravado
        execute_tool(g, "registrar_incidente", {"servico": alvo, "titulo": "x"}, permitir_escrita=False)
        falha("Protecao do modo acao", "Gravou sem permissao!")
    except PermissionError:
        ok("Protecao do modo acao (escrita bloqueada quando desligado)")
    except Exception as exc:
        falha("Protecao do modo acao", f"{type(exc).__name__}: {exc}")


def checar_web():
    try:
        from src import web
        c = web.app.test_client()
        a, b = c.get("/").status_code, c.get("/static/app.js").status_code
        (ok if (a, b) == (200, 200) else falha)("Interface web (pagina e script)", "" if (a, b) == (200, 200) else f"HTTP {a}/{b}")
        if c.post("/api/ask", json={"pergunta": ""}).status_code == 400:
            ok("Interface web valida perguntas vazias")
    except Exception as exc:
        falha("Interface web", f"{type(exc).__name__}: {exc}")


def checar_api():
    try:
        from dotenv import load_dotenv
        from anthropic import Anthropic
        load_dotenv(ROOT / ".env", override=True)
        modelo = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        Anthropic().messages.create(model=modelo, max_tokens=8, messages=[{"role": "user", "content": "ok"}])
        ok(f"API da Anthropic respondeu (modelo {modelo})")
    except Exception as exc:
        msg = str(exc)
        dica = ("Chave invalida: gere outra no console." if "401" in msg or "authentication" in msg.lower()
                else "Sem saldo? Veja Billing no console." if "credit" in msg.lower() or "balance" in msg.lower()
                else "Modelo inexistente? Ajuste ANTHROPIC_MODEL no .env." if "404" in msg or "not_found" in msg
                else msg[:160])
        falha("API da Anthropic", f"{type(exc).__name__}. {dica}")


def main():
    usar_api = "--api" in sys.argv
    checar_arquivos(); checar_dependencias()
    try:
        checar_env()
    except Exception as exc:
        falha(".env", f"{type(exc).__name__}: {exc}")
    checar_git(); checar_readme(); checar_web()
    g = checar_banco()
    if g is not None:
        checar_ferramentas(g)
    if usar_api:
        checar_api()
    else:
        aviso("API da Anthropic nao testada", "Rode com --api para testar a chave e o saldo (usa 1 chamada minima).")

    simbolo = {"OK": "[ OK  ]", "AVISO": "[AVISO]", "FALHA": "[FALHA]"}
    print()
    for st, titulo, dica in resultados:
        print(f"{simbolo[st]} {titulo}" + (f"\n         -> {dica}" if dica else ""))
    n = {s: sum(1 for r in resultados if r[0] == s) for s in simbolo}
    print(f"\nResumo: {n['OK']} ok, {n['AVISO']} avisos, {n['FALHA']} falhas.")
    if n["FALHA"]:
        print("O projeto NAO esta pronto: corrija as falhas acima.")
    elif n["AVISO"]:
        print("Funciona, mas ainda ha pendencias (avisos) para a entrega.")
    else:
        print("Tudo pronto.")
    sys.exit(1 if n["FALHA"] else 0)


if __name__ == "__main__":
    main()
