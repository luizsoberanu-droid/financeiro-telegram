# NEXUS Dark V4.3

Versão focada em modo ataque rígido para sair do negativo.

## Recursos
- Dashboard dark futurista
- Gráfico de gastos por categoria
- Categorias inteligentes: lanche/passeio/cinema -> lazer
- Análise rígida para dívida em 3 meses
- Contas com vencimento e alerta por dias úteis
- Edição de campos pelo painel
- Telegram webhook

## Deploy no Render
1. Suba todos os arquivos para a raiz do GitHub.
2. No Render, use Docker.
3. Configure `TELEGRAM_BOT_TOKEN` nas variables.
4. Faça deploy.
5. Configure o webhook:

`https://api.telegram.org/botSEU_TOKEN/setWebhook?url=https://SEUAPP.onrender.com/webhooks/telegram`

## Comandos no Telegram
- `/status`
- `/plano`
- `/analise`
- `/contas`
- `/vencimentos`
- `/pagar nome_da_conta`
- `/extra 300`
- `/editar lazer 120`
- `/editar cartao 250`
- `/divida iptu 300`
- `/posso 30 lanche`
- `lanche 25`
- `passeio 60`
