# Automação de Indicação de Condutor — PRF (SEI) + Jira + Drive

Fluxo: busca cards elegíveis no Jira → localiza os PDFs no Drive → abre o SEI
e monta o processo de "Identificação de condutor infrator" com os anexos.

## ⚠️ Antes de tudo

- Este script mexe com um sistema **jurídico oficial** (SEI da PRF). Rode
  sempre primeiro em **modo conferência** (padrão) e revise cada processo
  antes de qualquer envio real.
- Guarde `.env` só na sua máquina. Não compartilhe, não suba para
  nenhum repositório.
- Eu não tenho acesso ao site da PRF, então os seletores do SEI em
  `sei_automation.py` podem precisar de ajuste fino na primeira rodada —
  veja a seção "Se algo não clicar certo" abaixo.

## 1. Instalação (uma vez só)

Precisa ter Python 3.10+ instalado. Depois, no terminal, dentro da pasta do projeto:

```bash
pip install -r requirements.txt
playwright install chromium
```

## 2. Configuração

```bash
cp config.env.example .env
```

Edite `.env` e preencha:

- **SEI**: usuário e senha.
- **JIRA_API_TOKEN**: gere em https://id.atlassian.com/manage-profile/security/api-tokens
- **DRIVE_INDICACOES_ROOT**: caminho da pasta no seu computador onde o Google
  Drive Desktop sincroniza as pastas "Indicações <número>". Para achar:
  abra o Google Drive no seu PC, clique com botão direito na pasta
  "Indicações" > "Copiar caminho" (Windows) ou veja no Finder (Mac).

## 3. Testar com um único card antes de rodar tudo

```bash
python main.py BOBA-13450
```

Isso roda o fluxo completo só para esse card, com o navegador visível
(`HEADLESS=false`), parando antes do envio final para você conferir
(`MODO_CONFERENCIA=true`).

## 4. Rodar para todos os cards elegíveis

```bash
python main.py
```

## Como o script decide quais cards processar

- Projeto `BOBA`, status `In Execution`
- Campo "código do órgão" = `100`
- Nome do órgão contém "PRF" ou "Rodoviária Federal"

Se algum card que deveria aparecer não aparecer (ou aparecer um que não
devia), me mande o print do card no Jira que eu ajusto os filtros em
`jira_client.py`.

## Como os documentos são identificados na pasta do Drive

Pasta esperada: `Indicações <número do BOBA>` (ex.: `Indicações 13450`).
Dentro dela, o script procura por nome de arquivo (não sensível a maiúsculas/acentos):

| Documento | Padrões aceitos |
|---|---|
| CNH do condutor | `CNH COND.pdf`, `CNH Condutor.pdf`, qualquer coisa com "cnh" + "cond" |
| Contrato social | `cs.pdf`, ou qualquer nome com "contrato social" |
| Termo de responsabilidade | `Tr.pdf`, ou qualquer nome com "termo de responsabilidade" |

Para adicionar mais tipos de documento, edite o dicionário `PADROES_DOCUMENTOS`
em `drive_helper.py`.

## Se algo não clicar certo no SEI

O script tira screenshots automáticos na pasta `screenshots/` a cada etapa.
Se ele travar em algum ponto:

1. Veja o último screenshot salvo — mostra exatamente onde parou.
2. Me mande o print (ou descreva o que apareceu) que eu ajusto o seletor
   certo em `sei_automation.py`.
3. Alternativa: rode `playwright codegen <url do SEI>` no terminal — isso
   abre um navegador que grava seus cliques e gera o código Python real dos
   seletores, que eu posso incorporar direto no script.

## Estrutura dos arquivos

```
config.env.example   -> modelo de configuração (copiar para config.env)
requirements.txt     -> dependências Python
jira_client.py        -> busca e filtra cards no Jira
drive_helper.py       -> localiza pasta e classifica PDFs no Drive
sei_automation.py     -> automação do navegador no SEI (Playwright)
main.py               -> script principal, junta tudo
```
