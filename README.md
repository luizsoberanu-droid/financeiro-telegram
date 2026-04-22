# NEXUS DARK V4

Sistema financeiro com painel futurista, Telegram, gráficos e análise financeira básica.

## Deploy no Render
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Root Directory: deixe em branco

## Variáveis de ambiente
Use o conteúdo de `.env.example`.

## Webhook do Telegram
Depois do deploy:
`https://api.telegram.org/botSEU_TOKEN/setWebhook?url=https://SEUAPP.onrender.com/webhooks/telegram`

## Comandos do Telegram
- `/status`
- `/analise`
- `/previsao`
- `/reserva`
- `/limites`
- `/contas`
- `/editar luz 290`
- `/cartao 850`
- `gasolina 70`
