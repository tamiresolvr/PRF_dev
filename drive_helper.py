"""
drive_helper.py
Localiza, para cada BOBA, a pasta "Indicações <numero>" dentro da pasta raiz
sincronizada do Google Drive e classifica os PDFs encontrados por tipo de
documento (CNH do condutor, contrato social, termo de responsabilidade etc.)

Se depois vocês quiserem trocar para a API oficial do Google Drive (em vez de
depender da sincronização local), essa é a única parte do projeto que precisa
mudar — o resto do fluxo (Jira -> SEI) continua igual.
"""

import os
import re
from unidecode import unidecode

def encontrar_raiz_drive():
    """
    Procura automaticamente a pasta INDICAÇÕES
    independente da letra do Drive.
    """

    caminho_relativo = os.path.join(
        "Drives compartilhados",
        "INDICAÇÕES"
    )

    for letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        unidade = f"{letra}:\\"
        caminho = os.path.join(unidade, caminho_relativo)

        if os.path.isdir(caminho):
            return caminho

    return None

# Padrões de nome de arquivo -> tipo de documento.
# Adicione/ajuste livremente conforme os nomes reais forem aparecendo.
PADROES_DOCUMENTOS = {

    "formulario": [
        r"^form\b",
        r"formulario",
    ],

    "cnh_condutor": [
        r"cnh.*cond",
        r"cnh_cond",
    ],

    "cnh_proprietario": [
        r"cnh.*prop",
        r"cnh_prop"
    ],

    "cnh_procurador": [
        r"cnh.*proc",
        r"cnh_proc"
    ],
    "doc_proprietario": [
        r"doc.*prop",
        r"doc_prop"
    ],

    "doc_procurador": [
        r"doc.*proc",
        r"doc_proc"
    ],

    "contrato_social": [
        r"^cs\b",
        r"contrato.*social",
    ],

    "termo_responsabilidade": [
        r"^tr\b",
        r"termo.*responsab",
    ],

    "procuracao": [
        r"^proc\b",
        r"procuracao",
    ],

    "contrato_locacao": [
        r"^cl\b",
        r"contrato.*loc",
    ],
}


def _normalizar_nome_pasta(nome: str) -> str:
    return unidecode(nome).strip().lower()


def encontrar_pasta_boba(raiz: str, numero_boba: str) -> str | None:
    """
    Procura uma pasta cujo BOBA seja exatamente o número informado.
    Aceita formatos:
      BOBA 13684
      BOBA-13684
      BOBA:13684
      BOBA-13684: URGENTE...
    """

    if not os.path.isdir(raiz):
        return None

    padrao = re.compile(
        rf"\bBOBA[\s\-:]*{re.escape(numero_boba)}(?:\b|:|-|\s)",
        re.IGNORECASE
    )

    for nome in os.listdir(raiz):
        caminho = os.path.join(raiz, nome)

        if not os.path.isdir(caminho):
            continue

        if padrao.search(nome):
            return caminho

    return None

def classificar_documentos(pasta: str) -> dict:
    """
    Varre a pasta principal E TODAS AS SUBPASTAS recursivamente e retorna um dict:
    { "cnh_condutor": "/caminho/subpasta/CNH COND.pdf", ... }
    """
    encontrados = {}
    ignorados = []

    if not os.path.isdir(pasta):
        return {"_ignorados": []}

    # os.walk percorre a pasta principal e qualquer subpasta que existir
    for root, dirs, files in os.walk(pasta):
        # Ordena os arquivos para manter a consistência do resultado
        for arquivo in sorted(files):
            # Ignora arquivos temporários e não-PDFs
            if arquivo.startswith("~$") or arquivo.startswith(".") or not arquivo.lower().endswith(".pdf"):
                continue

            nome_norm = unidecode(arquivo).lower()
            casou = False

            for tipo, padroes in PADROES_DOCUMENTOS.items():
                for padrao in padroes:
                    if re.search(padrao, nome_norm):
                        caminho_completo = os.path.join(root, arquivo)
                        
                        if tipo not in encontrados:
                            encontrados[tipo] = caminho_completo
                        else:
                            ignorados.append(arquivo)
                        
                        casou = True
                        break
                if casou:
                    break

    encontrados["_ignorados"] = ignorados
    return encontrados

def montar_pacote_documentos(raiz: str, numero_boba: str) -> dict:
    print(f"BOBA recebido: {numero_boba}")

    pasta = encontrar_pasta_boba(raiz, numero_boba)

    print(f"Pasta encontrada: {pasta}")

    if pasta is None:
        return None

    docs = classificar_documentos(pasta)
    docs["_pasta"] = pasta
    return docs
