import requests


class SlackNotifier:

    def __init__(self, webhook_url):
        self.webhook_url = webhook_url


    def enviar(self, mensagem):

        resposta = requests.post(
            self.webhook_url,
            json={
                "text": mensagem
            }
        )

        resposta.raise_for_status()

        print("Mensagem enviada para Slack")