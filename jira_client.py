"""
jira_client.py
Busca no Jira os cards do projeto BOBA que precisam de indicação de condutor,
filtrando por status "In Execution" e órgão PRF (código 100).

Como o nome exato dos campos customizados (AIT, Placa, Nome do órgão) pode
variar, este módulo primeiro descobre os IDs dos campos pelo NOME (via
/rest/api/3/field) e depois usa esses IDs na busca. Isso evita ficar
"chutando" customfield_12345 no código.
"""

import requests
import time
from datetime import datetime
from unidecode import unidecode


def _norm(texto: str) -> str:
    """Normaliza texto para comparação: minúsculo, sem acento, sem espaço extra."""
    if texto is None:
        return ""
    return unidecode(str(texto)).strip().lower()


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (email, api_token)
        self.headers = {"Accept": "application/json"}

        teste = requests.get(
            f"{self.base_url}/rest/api/3/myself",
        headers=self.headers,
        auth=self.auth,
        )
        print("Teste de autenticação Jira:", teste.status_code)

        self._field_map = None  # nome_normalizado -> id do campo

    # ------------------------------------------------------------------
    def _carregar_campos(self):
        """Monta um mapa {nome_do_campo_normalizado: id_do_campo}."""
        if self._field_map is not None:
            return self._field_map

        resp = requests.get(
            f"{self.base_url}/rest/api/3/field",
            headers=self.headers,
            auth=self.auth,
        )
        resp.raise_for_status()
        campos = resp.json()

        mapa = {}
        for campo in campos:
            mapa[_norm(campo["name"])] = campo["id"]
        self._field_map = mapa
        return mapa

    def encontrar_campo(self, *pistas):
        """
        Procura o ID do campo cujo nome contenha alguma das 'pistas'
        (ex.: encontrar_campo("ait") acha "AIT", "Número AIT", "Nº AIT"...).
        Retorna o primeiro que bater, ou None se não achar nenhum.
        """
        mapa = self._carregar_campos()
        for nome_normalizado, campo_id in mapa.items():
            for pista in pistas:
                if _norm(pista) in nome_normalizado:
                    return campo_id
        return None

        # ------------------------------------------------------------------
    def buscar_issues(self, jql: str, campos_extra: list[str]):
        """
        Executa a busca JQL usando o endpoint novo do Jira Cloud.
        """
        issues = []
        next_page_token = None

        while True:
            body = {
                "jql": jql,
                "maxResults": 50,
                "fields": campos_extra,
            }

            if next_page_token:
                body["nextPageToken"] = next_page_token

            resp = requests.post(
                f"{self.base_url}/rest/api/3/search/jql",
                headers={**self.headers, "Content-Type": "application/json"},
                auth=self.auth,
                json=body,
            )

            print("Busca Jira:", resp.status_code)
            resp.raise_for_status()

            data = resp.json()
            
            print("TOTAL ENCONTRADO:", len(data.get("issues", [])))

            issues.extend(data.get("issues", []))

            next_page_token = data.get("nextPageToken")

            if not next_page_token:
                break

        return issues
    # ------------------------------------------------------------------
    def listar_cards_para_indicacao(self, jql: str):
        """
        Retorna uma lista de dicts prontos para uso:
        [{ "boba": "13450", "chave": "BOBA-13450", "ait": "...", "placa": "...",
           "status": "In Execution", "orgao_nome": "...", "orgao_codigo": "100" }, ...]

        Aplica os filtros extras que a JQL sozinha não garante 100%:
          - status == "In Execution"
          - nome do órgão contém "PRF" ou "POLICIA RODOVIARIA FEDERAL"
        Ajuste as listas AIT_PISTAS / PLACA_PISTAS / ORGAO_NOME_PISTAS abaixo
        se os nomes dos seus campos customizados forem diferentes.
        """
        AIT_PISTAS = ["ait", "auto de infra"]
        PLACA_PISTAS = ["placa"]
        ORGAO_NOME_PISTAS = ["nome do orgao", "nome órgão", "orgao"]
        ORGAO_CODIGO_PISTAS = ["codigo orgao", "código órgão", "codigo do orgao"]

        campo_ait = self.encontrar_campo(*AIT_PISTAS)
        campo_placa = self.encontrar_campo(*PLACA_PISTAS)
        campo_orgao_nome = self.encontrar_campo(*ORGAO_NOME_PISTAS)
        campo_orgao_codigo = self.encontrar_campo(*ORGAO_CODIGO_PISTAS)

        campos = ["summary", "status"]
        for c in (campo_ait, campo_placa, campo_orgao_nome, campo_orgao_codigo):
            if c:
                campos.append(c)

        issues = self.buscar_issues(jql, campos)

        resultado = []
        for issue in issues:
            chave = issue["key"]  # ex: "BOBA-13450"
            boba_numero = chave.split("-")[-1]
            fields = issue["fields"]
            

            status_nome = fields.get("status", {}).get("name", "")
            if _norm(status_nome) != _norm("In Execution"):
                continue  # só queremos In Execution

            orgao_codigo = fields.get(campo_orgao_codigo)

            if orgao_codigo is None:
               continue

            if float(orgao_codigo) != 100:
               continue

            orgao_nome_txt = "PRF"

            import re

            summary = fields.get("summary", "")

            m_ait = re.search(r"AIT\s+([A-Z0-9]+)", summary, re.IGNORECASE)
            m_placa = re.search(r"Placa\s+([A-Z0-9]+)", summary, re.IGNORECASE)

            ait = m_ait.group(1) if m_ait else ""
            placa = m_placa.group(1) if m_placa else ""
           
            resultado.append({
                "boba": boba_numero,
                "chave": chave,
                "ait": ait,
                "placa": placa,
                "status": status_nome,
                "orgao_nome": orgao_nome_txt,
            })

        return resultado
    
    def adicionar_comentario(self, issue_key: str, numero_processo: str):
                
                """
                Adiciona um comentário com o número do processo SEI.
            """

                url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"

                body = {
                    "body": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"Processo SEI: {numero_processo}"
                                    }
                                ]
                            }
                        ]
                    }
                }

                resp = requests.post(
                    url,
                    headers={
                        **self.headers,
                        "Content-Type": "application/json"
                    },
                    auth=self.auth,
                    json=body
                )

                resp.raise_for_status()

                print(f"Comentário adicionado em {issue_key}")  
    def atualizar_metodo_online(self, chave):
        """
        Atualiza o campo Método no Jira para 'Online'.
        """
        # ID do campo 'Método de Indicação' no seu Jira
        campo_metodo = "customfield_10621"
        url = f"{self.base_url}/rest/api/3/issue/{chave}"

        try:
            # Tenta atualizar assumindo que é uma lista de seleção (Select)
            payload = {
                "fields": {
                    campo_metodo: {"value": "Online"}
                }
            }

            resposta = requests.put(
                url,
                json=payload,
                headers=self.headers,
                auth=self.auth
            )

            # Se der erro (ex: se o campo for texto simples), tenta no formato Texto
            if resposta.status_code not in (200, 204):
                payload_texto = {
                    "fields": {
                        campo_metodo: "Online"
                    }
                }
                resposta = requests.put(
                    url,
                    json=payload_texto,
                    headers=self.headers,
                    auth=self.auth
                )

            resposta.raise_for_status()
            print(f"Método atualizado para Online em {chave}")

        except Exception as e:
            print(f"⚠️ Erro ao atualizar método em {chave}: {e}")

    def atualizar_data_indicacao(self, chave):
        """Atualiza a data de indicação para hoje."""
        campo_data = "customfield_10620"
        url = f"{self.base_url}/rest/api/3/issue/{chave}"
        hoje = datetime.now().strftime("%Y-%m-%d")
        payload = {"fields": {campo_data: hoje}}

        resposta = requests.put(
            url,
            json=payload,
            headers=self.headers,
            auth=self.auth
        )
        resposta.raise_for_status()
        print(f"Data de indicação atualizada em {chave}: {hoje}")

    def atualizar_status_em_andamento(self, chave):
        """Move o status para 'Enviada para órgão'."""
        url = f"{self.base_url}/rest/api/3/issue/{chave}/transitions"

        resposta = requests.get(
            url,
            headers=self.headers,
            auth=self.auth
        )
        resposta.raise_for_status()
        transicoes = resposta.json().get("transitions", [])

        transicao_id = None
        for t in transicoes:
            # Compara ignorando maiúsculas/minúsculas para não falhar
            if t["name"].strip().lower() == "enviada para órgão" or str(t["id"]) == "131":
                transicao_id = t["id"]
                break

        if transicao_id is None:
            print(f"ℹ️ Transição 'Enviada para órgão' não encontrada para {chave}.")
            return

        resposta = requests.post(
            url,
            headers=self.headers,
            auth=self.auth,
            json={"transition": {"id": transicao_id}}
        )
        resposta.raise_for_status()
        print(f"Status atualizado para Enviada para órgão em {chave}")