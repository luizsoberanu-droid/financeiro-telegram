# Financeiro Telegram Premium

Sistema premium para **controle financeiro pessoal com Telegram**, planilha detalhada e painel web futurista.

## O que está incluído
- `financeiro_telegram_premium.xlsx` — planilha detalhada com orçamento, limites, contas fixas, lançamentos, fluxo de caixa e planejamento
- `app.py` — servidor Flask com painel web, APIs e webhook do Telegram
- `spreadsheet_engine.py` — motor de cálculo e gravação na planilha
- `notifier.py` — envio de mensagens pelo Telegram ou modo log
- `templates/` + `static/` — interface futurista
- `.env.example` — configuração pronta
- `Dockerfile` — deploy online
- `start_local.bat` — inicialização simples no Windows

## O que ele faz
- recebe lançamentos pelo Telegram em tempo real
- calcula gasto, limite e saldo da categoria
- avisa quando estiver perto ou acima do limite
- mostra o status geral do mês
- lista contas próximas do vencimento
- permite marcar conta como paga com um comando
- mantém tudo registrado na planilha

## Comandos principais
- `/gasto gasolina 120 shell`
- `gasolina 120`
- `/receita extra 500 freela`
- `/status`
- `/status carro`
- `/limites`
- `/contas`
- `/pagar internet e celular`
- `/ajuda`

## Como rodar localmente
### Windows
1. Instale Python 3.11+.
2. Extraia a pasta.
3. Dê duplo clique em `start_local.bat`.

### Manual
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

## Painel web
- `http://localhost:5000`

## Como ligar no Telegram
1. Abra o Telegram.
2. Procure por **BotFather**.
3. Use `/newbot`.
4. Copie o token gerado.
5. Preencha no `.env`:
   - `TELEGRAM_PROVIDER=telegram`
   - `TELEGRAM_BOT_TOKEN=SEU_TOKEN`
   - `TELEGRAM_CHAT_ID=SEU_CHAT_ID`

## Como descobrir o chat_id
1. Rode o sistema localmente.
2. Envie qualquer mensagem para o bot.
3. Abra no navegador:
   - `https://api.telegram.org/botSEU_TOKEN/getUpdates`
4. Ache o campo `chat.id` e copie para o `.env`.

## Como subir online
- Render
- Railway
- VPS com Docker

### Webhook do Telegram
Depois que o app estiver online, configure:
```text
https://api.telegram.org/botSEU_TOKEN/setWebhook?url=https://SEUAPP/webhooks/telegram
```

## Observações
- Os dias de vencimento podem ser ajustados na aba `Contas_Fixas`.
- Os limites mensais podem ser ajustados na aba `Limites`.
- O sistema trabalha melhor com uma rotina de uso diária ou semanal.

## Arquitetura
- Flask
- OpenPyXL
- Requests
- APScheduler
- Telegram Bot API
