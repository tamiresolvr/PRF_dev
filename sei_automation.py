"""
sei_automation.py
Automação do peticionamento no SEI da PRF usando Playwright.
"""
import os
import time
from pathlib import Path
import sys 

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

load_dotenv()

print("URL TESTE:", os.getenv("URL_SEI"))

def encontrar_chromium():
    caminhos = []

    # Quando está rodando como .exe (PyInstaller)
    if getattr(sys, "frozen", False):
        base_app = Path(sys._MEIPASS)
    else:
        base_app = Path(__file__).parent

    # Chromium entregue junto com a automação
    caminhos.append(
        base_app / "ms-playwright"
    )

    # Chromium instalado pelo Playwright no usuário
    if "LOCALAPPDATA" in os.environ:
        caminhos.append(
            Path(os.environ["LOCALAPPDATA"]) / "ms-playwright"
        )

    for base in caminhos:
        if not base.exists():
            continue

        for pasta in base.glob("chromium-*"):
            chrome = pasta / "chrome-win" / "chrome.exe"

            if chrome.exists():
                return str(chrome)

    return None




    

    return None

SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _screenshot(page, nome):
    caminho = os.path.join(SCREENSHOT_DIR, f"{nome}_{int(time.time())}.png")

    try:
        page.screenshot(path=caminho, full_page=True)
        print(f"   [screenshot salvo em {caminho}]")

    except Exception:
        pass


def montar_especificacao(ait, placa):
    return f"Indicação de Condutor AIT {ait} " f"- Placa {placa}"


class SEIAutomation:

    def __init__(
        self,
        url_login: str,
        usuario: str,
        senha: str,
        headless: bool = False,
        modo_conferencia: bool = True,
    ):

        self.url_login = url_login
        self.usuario = usuario
        self.senha = senha
        self.headless = headless
        self.modo_conferencia = modo_conferencia

        self._pw = None
        self.browser = None
        self.context = None
        self.page = None

    def iniciar(self):

        self._pw = sync_playwright().start()

        chromium_path = encontrar_chromium()

        print("Chromium encontrado:", chromium_path)


        self.browser = self._pw.chromium.launch(
        executable_path=chromium_path,
        headless=self.headless,
        slow_mo=150
        )

        self.context = self.browser.new_context()

        self.page = self.context.new_page()

    def encerrar(self):

        if self.context:
            self.context.close()

        if self.browser:
            self.browser.close()

        if self._pw:
            self._pw.stop()

    def login(self):

        page = self.page

        print("-> Abrindo SEI e fazendo login...")
        print("URL recebida:", repr(self.url_login))

        page.goto(self.url_login, wait_until="load")

        page.get_by_role("textbox", name="E-mail").wait_for(
            state="visible", timeout=15000
        )

        page.get_by_role("textbox", name="E-mail").fill(self.usuario)

        page.get_by_role("textbox", name="Senha").fill(self.senha)

        page.get_by_role("button", name="ENTRAR").click()

        page.wait_for_load_state("networkidle")

        _screenshot(page, "01_apos_login")

        print("   Login realizado.")

    def abrir_peticionamento_processo_novo(self):

        page = self.page

        print("-> Indo em Peticionamento > Processo Novo...")

        page.get_by_text("Peticionamento", exact=False).first.click()

        page.wait_for_timeout(800)

        page.get_by_text("Processo Novo", exact=False).first.click()

        page.wait_for_load_state("networkidle")

        _screenshot(page, "02_processo_novo")

    def selecionar_tipo_processo(self):

        page = self.page

        print("-> Selecionando Identificação de Condutor")

        page.get_by_role("link", name="Identificação de Condutor").click()

        page.wait_for_load_state("networkidle")

        _screenshot(page, "03_tipo_processo")

    def preencher_especificacao(self, texto_especificacao: str):

        page = self.page

        print(f"-> Preenchendo especificação: {texto_especificacao}")

        campo = page.locator("#txtEspecificacao")

        try:

            campo.wait_for(state="visible", timeout=8000)

            campo.fill(texto_especificacao)

        except PWTimeout:

            page.get_by_label("Especificação").fill(texto_especificacao)

        _screenshot(page, "04_especificacao")

    def salvar_processo(self):

        page = self.page

        print("-> Salvando processo...")

        try:

            page.locator("#btnSalvar").click(timeout=3000)

        except PWTimeout:

            page.get_by_role("button", name="Salvar").click()

        page.wait_for_load_state("networkidle")

        _screenshot(page, "05_salvo")

    def anexar_documentos(self, documentos: dict):

        page = self.page

        print("-> Anexando documentos no SEI")

        # -----------------------------
        # Documento Principal
        # -----------------------------

        if documentos.get("formulario"):

            print("   Enviando FORM")

            page.get_by_role(
                "button", name="Documento Principal (5 Mb):"
            ).set_input_files(documentos["formulario"])

            page.locator("#complementoPrincipal").fill(documentos.get("_ait", ""))

            page.locator("#frmDocumentoPrincipal").get_by_text(
                "Nato-digital", exact=False
            ).click()

            page.locator("#camposDigitalizadoPrincipalBotao").get_by_role(
                "button", name="Adicionar"
            ).click()
            

            # espera o SEI processar este documento antes do próximo
            page.wait_for_timeout(3000)

        # -----------------------------
        # Documentos Essenciais
        # -----------------------------

        essenciais = [
            ("cnh_condutor", "506", "CNH COND"),
            ("cnh_proprietario", "509", "CNH PROP"),
            ("cnh_procurador", "509", "CNH PROC"),
            ("doc_proprietario", "509", "DOC PROP"),
            ("doc_procurador", "509", "DOC PROC"),
        ]

        for chave, tipo, descricao in essenciais:

            if not documentos.get(chave):
                continue

            print(f"   Enviando {descricao}")

            page.get_by_role(
                "button", name="Documento Essencial (10 Mb):"
            ).set_input_files(documentos[chave])

            page.locator("#tipoDocumentoEssencial").select_option(tipo)

            page.locator("#complementoEssencial").fill(descricao)

            page.locator("#frmDocumentosEssenciais label").filter(
                has_text="Nato-digital"
            ).first.click()

            page.locator("#camposDigitalizadoEssencialBotao").get_by_role(
                "button", name="Adicionar"
            ).click()
            print(f"   Aguardando processamento do {descricao}...")
            page.wait_for_timeout(5000)

        # -----------------------------
        # Documentos Complementares
        # -----------------------------

        complementares = [
            ("contrato_social", "554", "CONTRATO SOCIAL"),
            ("termo_responsabilidade", "442", "TERMO DE RESPONSABILIDADE"),
            ("contrato_locacao", "513", "CONTRATO DE LOCAÇÃO"),
            ("procuracao", "60", "PROCURAÇÃO"),
        ]

        for chave, tipo, descricao in complementares:

            if not documentos.get(chave):
                continue

            print(f"   Enviando {descricao}")

            page.get_by_role(
                "button", name="Documentos Complementares (10 Mb):"
            ).set_input_files(documentos[chave])

            page.wait_for_timeout(3000)

            page.locator("#tipoDocumentoComplementar").select_option(tipo)

            page.locator("#complementoComplementar").fill(descricao)

            page.locator("#frmDocumentosComplementares label").filter(
                has_text="Nato-digital"
            ).first.click()


            page.locator("#camposDigitalizadoComplementarBotao").get_by_role(
                "button", name="Adicionar"
            ).click()


            print(f"   Aguardando processamento do {descricao}...")
            page.wait_for_timeout(5000)

        # espera o SEI processar os anexos
        page.wait_for_timeout(3000)

        _screenshot(page, "06_documentos_anexados")

        print("-> Documentos anexados com sucesso")
        print("===== FIM DOS ANEXOS =====")

    def validar_documentos_anexados(self, documentos: dict):

        page = self.page

        print("-> Validando documentos anexados no SEI")

        texto = page.locator("body").inner_text().upper()

        faltando = []

        obrigatorios = []

        if documentos.get("formulario"):
            obrigatorios.append("FORM")

        if documentos.get("cnh_condutor"):
            obrigatorios.append(
                ["CNH", "COND"])

        if documentos.get("contrato_social"):
            obrigatorios.append("CONTRATO SOCIAL")

        if documentos.get("procuracao"):
            obrigatorios.append("PROCURAÇÃO")

        for doc in obrigatorios:
            if isinstance(doc, list):
                encontrado = all(
                palavra in texto
                for palavra in doc
                )
                if not encontrado:
                   faltando.append("CNH COND")
        else:
            if doc not in texto:
                faltando.append(doc)
                

        if faltando:

            print(
                f"-> Documentos ausentes no SEI: {faltando}"
            )

            return False


        print(
            "-> Todos os documentos conferidos no SEI"
        )

        return True

    def peticionar(self):
        page = self.page

        print("===== INÍCIO PETICIONAMENTO =====")

        # Clica em Peticionar
        page.locator("#divInfraBarraComandosInferior").get_by_role(
            "button", name="Peticionar"
        ).click()

        # Modal
        modal = page.frame_locator('iframe[name="modal-frame"]')

        # Seleciona Cidadão
        modal.locator("#selCargo").select_option(label="Cidadão")

        # Preenche a senha
        modal.locator("#pwdsenhaSEI").fill(self.senha)

        # Aguarda o overlay do SEI desaparecer
        page.locator("#divInfraAvisoFundo").wait_for(
        state="hidden",
        timeout=15000
        )

        # Assina
        modal.get_by_role(
        "button",
        name="Assinar"
        ).click()

        # Aguarda o SEI concluir o processamento
        page.wait_for_timeout(10000)

        page.wait_for_load_state("networkidle")

    def capturar_numero_processo(self):

        page = self.page

        print("-> Capturando número do processo...")

        # Aguarda carregamento da tela de confirmação
        page.wait_for_load_state("networkidle")

        import re

        # Espera até 30 segundos pelo protocolo aparecer
        for _ in range(30):

            texto = page.locator("body").inner_text()

            resultado = re.search(
                r"\d{5}\.\d{6}/\d{4}-\d{2}",
                texto
            )

            if resultado:

                numero = resultado.group(0)

                print(f"-> Processo SEI encontrado: {numero}")

                return numero

            page.wait_for_timeout(1000)

        page.screenshot(
            path="screenshots/erro_captura_processo.png",
            full_page=True
        )

        raise Exception(
            "Número do processo não encontrado no SEI"
        )

    def finalizar(self):
        """
        Último passo.

        Se modo_conferencia estiver ativo,
        o navegador fica aberto para conferência manual.
        """

        if self.modo_conferencia:

            print("\n=== MODO CONFERÊNCIA ATIVO ===")

            print("Revise o processo e envie manualmente.")

            input("Pressione ENTER para encerrar e fechar o navegador...")

        else:

            print("-> Enviando processo automaticamente...")

            page = self.page

            try:

                page.get_by_role("button", name="Enviar").click(timeout=5000)

            except PWTimeout:

                page.get_by_text("Concluir", exact=False).first.click()

            page.wait_for_load_state("networkidle")

            _screenshot(page, "07_enviado")
