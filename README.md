# NEXUS DARK V4.7

Versão com base inicial carregada, contas fixas, cartões separados, parcelas e edição pelo painel.

## Novidades
- base inicial já cadastrada
- editar contas, cartões e parcelas direto no painel
- marcar conta/cartão como pago ou aberto
- alertas de vencimento por dias úteis
- análise rígida para saída do negativo

## Render
- Build: pip install -r requirements.txt
- Start: gunicorn app:app

## Variáveis
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

Depois do deploy, refaça o webhook do Telegram.
