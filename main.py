import os
import sys

# =========================================================
# CONFIGURAÇÃO DO PLAYWRIGHT PARA .EXE ÚNICO (ONEFILE)
# =========================================================
if getattr(sys, "frozen", False):
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(base_dir, "ms-playwright")
# =========================================================

import time
import schedule
import csv         
import calendar    
from datetime import datetime
from dotenv import load_dotenv
from jira_client import JiraClient
from drive_helper import montar_pacote_documentos, encontrar_raiz_drive 
from sei_automation import SEIAutomation
from slack_notifier import SlackNotifier

def carregar_config():

    load_dotenv(".env")

    obrigatorias = [
        "SEI_URL",
        "SEI_USUARIO",
        "SEI_SENHA",
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
        "JIRA_JQL",
        "SLACK_WEBHOOK_URL",
    ]

    faltando = [
        item
        for item in obrigatorias
        if not os.getenv(item)
    ]

    if faltando:
        print(
            f"ERRO: faltam variáveis: {', '.join(faltando)}"
        )
        sys.exit(1)

    return {
        item: os.getenv(item)
        for item in obrigatorias
    } | {
        "HEADLESS": os.getenv(
            "HEADLESS",
            "false"
        ).lower() == "true",

        "MODO_CONFERENCIA": os.getenv(
            "MODO_CONFERENCIA",
            "true"
        ).lower() == "true",
    }

import csv
import calendar
from datetime import datetime

def registrar_em_csv(boba_key, ait, placa, num_processo):
    agora = datetime.now()
    # Cria um arquivo com o nome do mês atual, ex: relatorio_sei_2026_08.csv
    nome_arquivo = f"relatorio_sei_{agora.strftime('%Y_%m')}.csv"
    arquivo_existe = os.path.exists(nome_arquivo)
    
    with open(nome_arquivo, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file, delimiter=';')
        if not arquivo_existe:
            writer.writerow(["Data/Hora", "Card Jira", "AIT", "Placa", "Processo SEI"])
        
        writer.writerow([
            agora.strftime("%Y-%m-%d %H:%M:%S"),
            boba_key,
            ait,
            placa,
            num_processo
        ])
    print(f"📊 Card {boba_key} registrado no relatório CSV ({nome_arquivo}).")

def checar_e_notificar_fim_de_mes(slack):
    hoje = datetime.now()
    ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
    
    # Se hoje for o último dia do mês
    if hoje.day == ultimo_dia:
        nome_arquivo = f"relatorio_sei_{hoje.strftime('%Y_%m')}.csv"
        slack.enviar(f"📅 *Atenção:* Hoje é o último dia do mês! O relatório consolidado `{nome_arquivo}` está salvo na pasta da automação.")
def main():

    cfg = carregar_config()
    raiz_drive = encontrar_raiz_drive()
    if raiz_drive is None:
        raise Exception(
            "Pasta INDICAÇÕES não encontrada no computador."
        )

    print(f"Drive INDICAÇÕES encontrado: {raiz_drive}")

    filtro_chave = (
        sys.argv[1:]
        if len(sys.argv) > 1
        else None
    )

    # =========================
    # 1 - BUSCA JIRA
    # =========================

    print("== 1. Buscando cards no Jira ==")

    jira = JiraClient(
        cfg["JIRA_BASE_URL"],
        cfg["JIRA_EMAIL"],
        cfg["JIRA_API_TOKEN"]
    )
    slack = SlackNotifier(
        cfg["SLACK_WEBHOOK_URL"]
    )

    cards = jira.listar_cards_para_indicacao(
        cfg["JIRA_JQL"]
    )

    if filtro_chave:
        cards = [
            c
            for c in cards
            if c["chave"] in filtro_chave
        ]

    if not cards:
        print("\n========================================")
        print("✅ Nenhum card elegível encontrado.")
        print("A automação foi encerrada normalmente.")
        print("========================================")
        return

    for c in cards:
        print(
            f" - {c['chave']} | "
            f"AIT: {c['ait']} | "
            f"Placa: {c['placa']}"
        )

    # =========================
    # 2 - VALIDA DRIVE
    # =========================

    print(
        "\n== 2. Conferindo documentos no Drive =="
    )

    pacotes = {}

    DOCUMENTOS_OBRIGATORIOS = [
        "formulario",
        "cnh_condutor",
        "contrato_social",
    ]

    DOCUMENTOS_PROP_PROC = [
        "cnh_proprietario",
        "doc_proprietario",
        "cnh_procurador",
        "doc_procurador",
        "procuracao",
    ]

    for c in cards:

        pacote = montar_pacote_documentos(
            raiz_drive,
            c["boba"]
        )

        if pacote is None:

            mensagem = (
                "Automação bloqueada. "
                "Pasta não encontrada no Drive."
            )
            slack.enviar(
                f"""
        ❌ Automação bloqueada

        Card: {c['chave']}

        Motivo:
        {mensagem}
        """
            )

            print(
                f"[BLOQUEADO] {c['chave']}"
            )

            jira.adicionar_comentario(
                c["chave"],
                mensagem
            )

            continue

        faltando = []

        # Confere documentos obrigatórios
        for doc in DOCUMENTOS_OBRIGATORIOS:
            if doc not in pacote:
                faltando.append(doc)

        # Confere PROP ou PROC
        tem_prop_proc = any(
            doc in pacote
            for doc in DOCUMENTOS_PROP_PROC
        )

        if not tem_prop_proc:
            faltando.append(
                "documento PROP/PROC"
            )

        if faltando:

            mensagem = (
                "Automação bloqueada. "
                "Documentos faltantes: "
                + ", ".join(faltando)
            )

            slack.enviar(
                f"""
    ❌ Automação bloqueada

    Card: {c['chave']}

    Motivo:
    {mensagem}
    """
            )
            print(
                f"[BLOQUEADO] "
                f"{c['chave']}: {mensagem}"
            )

            jira.adicionar_comentario(
                c["chave"],
                mensagem
            )

            continue

        # Guarda pacote completo
        pacotes[c["chave"]] = pacote

        documentos_encontrados = [
            doc
            for doc in pacote
            if not doc.startswith("_")
        ]

        print(
            f"[OK] {c['chave']} documentos:"
        )

        print(
            documentos_encontrados
        )

    cards_prontos = [
        c
        for c in cards
        if c["chave"] in pacotes
    ]

    if not cards_prontos:
        print(
            "Nenhum card pronto para envio."
        )
        return

    # =========================
    # 3 - SEI
    # =========================

    print(
        f"\n== 3. Abrindo SEI para "
        f"{len(cards_prontos)} card(s) =="
    )

    sei = SEIAutomation(
        url_login=cfg["SEI_URL"],
        usuario=cfg["SEI_USUARIO"],
        senha=cfg["SEI_SENHA"],
        headless=cfg["HEADLESS"],
        modo_conferencia=cfg["MODO_CONFERENCIA"]
    )

    try:

        print("Iniciando Playwright...")
        sei.iniciar()
        print("Playwright iniciado com sucesso.")

        print("Fazendo login no SEI...")
        sei.login()

        for c in cards_prontos:

            print(
                f"\n--- Processando {c['chave']} ---"
            )

            sei.abrir_peticionamento_processo_novo()
            sei.selecionar_tipo_processo()

            especificacao = (
                f"Indicação de Condutor "
                f"AIT {c['ait']} - "
                f"Placa {c['placa']}"
            )

            sei.preencher_especificacao(
                especificacao
            )

            pacote = pacotes[c["chave"]]
            pacote["_ait"] = c["ait"]

            # Envia todos os documentos do Drive
            sei.anexar_documentos(
                pacote
            )

            time.sleep(3)

            documentos_ok = sei.validar_documentos_anexados(pacote)

            if not documentos_ok:

                mensagem = (
                    "Automação bloqueada. "
                    "Documentos não foram anexados corretamente no SEI."
                )
                slack.enviar(
                    f"""
                    ❌ Automação bloqueada

                    Card: {c['chave']}

                    Motivo:
                    {mensagem}
                    """
                )

                print(
                    f"[ERRO] {c['chave']}: {mensagem}"
                )

                jira.adicionar_comentario(
                    c["chave"],
                    mensagem
                ) 

                continue 

            print(
                "Documentos conferidos. Peticionando..."
            )

            sei.peticionar()

            numero_processo = (
                sei.capturar_numero_processo()
            )

            print(
                f"Processo SEI gerado: {numero_processo}"
            )

            jira.adicionar_comentario(
                c["chave"],
                f"Processo SEI gerado: {numero_processo}"
            )

            jira.atualizar_metodo_online(
                c["chave"]
            )

            jira.atualizar_data_indicacao(
                c["chave"]
            )
            
            jira.atualizar_status_em_andamento(
                c["chave"]
            )
            
            slack.enviar(
                f"""
            ✅ Indicação enviada para órgão

            Card: {c['chave']}
            AIT: {c['ait']}
            Placa: {c['placa']}
            Processo SEI: {numero_processo}
            Método: Online
            Status: ENVIADA PARA ÓRGÃO
            """
            )
            registrar_em_csv(c['chave'], c['ait'], c['placa'], numero_processo)

    except Exception as e:
        print("\n========== ERRO ==========")
        print(type(e).__name__)
        print(e)
        slack.enviar(f"⚠️ Atenção: Ocorreu uma falha no processamento: {e}")

    finally:
        sei.encerrar()
    checar_e_notificar_fim_de_mes(slack)
    
    print(
        "\nConcluído."
    )


def executar_job():
    print(f"\n⏰ [{time.strftime('%H:%M:%S')}] Iniciando ciclo automático de verificação...")
    try:
        main()
    except Exception as e:
        print(f"❌ Erro na execução automática: {e}")


if __name__ == "__main__":

        
    # Executa uma vez imediatamente ao abrir o script
    executar_job()

    # Configura para rodar a cada 30 minutos (ajuste se preferir outro tempo)
    schedule.every(30).minutes.do(executar_job)

    print("\n🤖 Robô iniciado com sucesso! Aguardando próxima execução...")

    while True:
        schedule.run_pending()
        time.sleep(60)