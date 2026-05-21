# 🚀 NEXUS AI v2.2

Assistente financeiro pessoal com **Inteligência Artificial REAL**, **alertas automáticos**, **PWA para celular** e **relatórios PDF**.
100% gratuito, 100% open source.

---

## ✨ NOVIDADES v2.2

| Recurso | Descrição |
|---------|-----------|
| 📱 **PWA** | Instale no celular como app nativo |
| 📄 **Relatórios PDF** | Gere relatórios mensais em PDF com um clique |
| 🔔 **Alertas Automáticos** | Alertas no Telegram: vencimentos, limites, saldo negativo |
| 📊 **Painel Completo** | Contas, cartões, gastos, lista de desejos, configurações |
| 🤖 **IA Real** | LLM com Function Calling (Groq/Google) |

---

## 🆓 100% GRATUITO

| Serviço | Site | Custo |
|---------|------|-------|
| **Groq** | [console.groq.com](https://console.groq.com) | R$ 0 |
| **Google AI Studio** | [aistudio.google.com](https://aistudio.google.com) | R$ 0 |
| **Render** | [render.com](https://render.com) | R$ 0 |
| **SQLite** | Já vem no Python | R$ 0 |

---

## 📱 INSTALAR NO CELULAR (PWA)

### Android (Chrome):
1. Acesse o site no Chrome
2. Toque nos **3 pontos** (menu)
3. Selecione **"Adicionar à tela inicial"**
4. Pronto! O app aparece como ícone nativo

### iPhone (Safari):
1. Acesse o site no Safari
2. Toque no botão **Compartilhar** (quadrado com seta)
3. Role para baixo e toque **"Adicionar à Tela de Início"**
4. Pronto!

---

## 📄 GERAR RELATÓRIO PDF

### No Painel Web:
1. Clique no botão **"📄 PDF Mensal"** no topo
2. O PDF baixa automaticamente
3. Contém: resumo, contas, gastos, dívidas, recomendações da IA

### Automaticamente:
- Relatorios e alertas do Telegram ficam desligados por padrao.
- Para reativar programacoes, configure `TELEGRAM_AUTOMATIONS_ENABLED=true`.

### No Telegram:
- Converse com a IA para revisar o fechamento do mes.
- Para baixar o PDF, use o painel web.

---

## 🔔 ALERTAS AUTOMÁTICOS

### O que você recebe no Telegram:

| Quando | Alerta |
|--------|--------|
| **Todo dia 9h** | Check-up geral de finanças |
| **Todo dia 8h** | Contas que vencem em 1-3 dias |
| **Dia 1 e 15** | Lembrete de reserva de emergência |
| **Dia 5, 15, 25** | Check-up de dívidas |
| **Quando estourar** | Limite de categoria excedido |
| **Quando saldo < 0** | Alerta de saldo negativo |
| **Último dia do mês** | Relatório mensal pronto |
| **Domingo 10h** | Resumo semanal de dívidas |

### Testar alertas:
- No painel, clique em **"🔔 Testar Alerta"**
- No Telegram, peça em linguagem natural para a IA verificar alertas.

---

## 🚀 DEPLOY NO RENDER

### 1. Variáveis de Ambiente:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
```

### 2. Webhook Telegram:
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<APP>.onrender.com/webhooks/telegram
```

### 3. Pronto! O app funciona em 2 minutos.

---

## 🤖 TELEGRAM COM IA CONVERSACIONAL

O Telegram nao depende mais de comandos fixos. A IA entende a intencao, pergunta o que faltar e salva no banco quando for uma acao financeira.

| Exemplo | O que acontece |
|---------|----------------|
| `lanche 25` | Pergunta se foi dinheiro/pix/debito ou cartao e salva o lancamento |
| `meu limite do Nubank e R$ 5000` | Registra o limite real do cartao |
| `quanto posso gastar no cartao este mes?` | Mostra limite real, limite seguro, uso e disponivel |
| `quero comprar celular de R$ 2500` | Salva na lista de desejos e analisa quando pode comprar |
| Qualquer texto | A IA analisa sua renda, dividas, reserva e estrategia |

---

## 🎯 FUNCIONALIDADES DO PAINEL

### 📋 Contas Fixas
- Adicionar, editar, excluir
- Marcar como paga/aberta
- Dia do vencimento e categoria

### 💳 Cartões
- Adicionar com **melhor dia de compra**
- Vencimento da fatura
- Limite ideal
- Marcar como pago

### 💸 Gastos
- Lançar com descrição, valor, categoria
- Dinheiro/Pix ou Cartão
- Histórico completo

### 🎯 Lista de Desejos
- Adicionar itens com preço desejado
- **IA monitora** quando você pode comprar
- Indicador visual: 🟢 pode comprar / 🟡 quase / 🔴 aguarde
- Prioridade: alta/média/baixa

### ⚙️ Configurações
- Renda fixa e extra
- Meta e valor atual da reserva
- Limites de categoria
- Dívidas

---

## 📊 ESTRUTURA DO PROJETO

```
nexus-ai/
├── app.py                    # Entry point + PWA + Cron
├── requirements.txt
├── models/
│   └── database.py           # SQLite + SQLAlchemy
├── services/
│   ├── ai_service.py         # LLM + Function Calling
│   ├── finance_service.py    # Lógica financeira
│   ├── alert_service.py      # Alertas Telegram
│   └── pdf_service.py        # Geração de PDF
├── routes/
│   ├── api.py                # API REST completa
│   └── telegram.py           # Bot Telegram
├── utils/
│   ├── helpers.py            # Funções utilitárias
│   └── cron_jobs.py          # Cron jobs automáticos
└── templates/
    ├── dashboard.html        # Painel web completo
    ├── manifest.json         # PWA manifest
    └── sw.js                 # Service Worker
```

---

## 📄 LICENÇA

MIT License — Use, modifique e distribua livremente.

**Feito com ❤️ para quem quer controlar as finanças sem pagar nada.**


## Histórico mensal automático

Esta versão salva o resumo mensal automaticamente em uma tabela `resumo_mensal`, sem alterar o layout do painel.

O saldo agora funciona como conta de banco: cada mes guarda `saldo_inicial`,
`movimento_mes` e `saldo_final`. O saldo inicial vem do saldo final do mes
anterior, e voce pode calibrar a situacao financeira de hoje pelo painel ou
falando no Telegram algo como `meu saldo hoje e R$ 1200`.

Endpoints:
- `GET /api/historico_mensal`
- `POST /api/historico_mensal/atualizar`

Telegram:
- Pergunte em linguagem natural pelo historico mensal.



## NEXUS AI v6 — Disciplina pesada + backup completo

Novidades:
- IA do Telegram com fallback: se Google/Groq falhar, responde por regras financeiras.
- Lançamento pelo Telegram agora pergunta se foi dinheiro/pix ou cartão.
- Compras no cartão entram como lançamento e aparecem na aba `faturas_cartao_credito` da planilha.
- Backup Google Sheets grava todas as abas principais e faturas de cartão.
- Robô de 5 minutos via `SELF_URL` e endpoint `/api/ping`.

Variável opcional para ping:
```
SELF_URL=https://SEU-APP.onrender.com
```

Para manter Render Free acordado com maior estabilidade, use também UptimeRobot a cada 5 minutos apontando para `/api/ping`.


## NEXUS AI v7 — Cartao alimentacao + Cofre vitalicio

Novidades desta melhoria:
- Saldo do cartao alimentacao no dashboard principal.
- Aba dedicada para configurar saldo, recarga mensal e dia de recarga.
- Registro de uso, recarga e ajuste do cartao alimentacao sem baguncar o saldo em dinheiro.
- No Telegram conversacional, pergunte sobre saldo do cartao alimentacao ou salvamento para a IA consultar e orientar.
- Aba `Cofre` no painel com tres camadas:
  - SQLite para uso diario.
  - Google Sheets como espelho permanente.
  - Snapshot JSON portatil para guardar fora do app.
- Autosave de apontamentos: cada operacao importante `POST/PUT/DELETE` vira um registro na tabela `apontamentos`, com origem, entidade, resumo e data.

Novos endpoints:
- `GET /api/alimentacao`
- `POST /api/alimentacao/config`
- `POST /api/alimentacao/movimento`
- `GET /api/salvamento/status`
- `GET /api/apontamentos`
- `POST /api/salvamento/google_sheets`
- `POST /api/salvamento/restaurar_google_sheets`
- `GET /api/salvamento/snapshot`
- `POST /api/salvamento/restaurar_snapshot`

Rotina recomendada:
1. Use o app normalmente no dia a dia.
2. Depois de grandes alteracoes, clique em `Salvar agora no Google Sheets`.
3. No fechamento do mes, baixe o `snapshot JSON`.
4. Se o Render reiniciar com banco vazio, restaure pelo Google Sheets.


## NEXUS AI v8 — Telegram como analista patrimonial

O Telegram agora deixa de funcionar como um menu de comandos programados e passa a responder como conversa direta com IA.

Exemplos de perguntas:
- `Analise minha renda e diga minha estrategia de crescimento`
- `Posso parcelar um celular de R$ 2500 em 10x?`
- `Quero comprar uma casa de R$ 1.000.000 em 10 anos, qual plano?`
- `Veja o mercado atual e monte um radar de investimentos`
- `Qual deve ser minha prioridade este mes para prosperar?`

Novas capacidades da IA:
- visao patrimonial com renda, divida, reserva e fase financeira;
- simulacao de metas grandes com aporte mensal necessario;
- analise de compra parcelada com impacto na fatura e na meta;
- radar de mercado com indices, dolar, ETFs e acoes brasileiras via cotacoes publicas;
- orientacao de investimento com risco, prazo, liquidez e diversificacao, sem promessa de retorno.

Integracoes conversacionais no Telegram:
- `lanche 25` ou `comprei lanche de R$ 25`: a IA pergunta se foi dinheiro/pix/debito ou cartao e salva o lancamento.
- `meu limite do Nubank e R$ 5000`: registra o limite real do cartao.
- `quanto posso gastar no cartao este mes?`: mostra limite real, limite seguro mensal, uso atual e disponivel.
- `quero comprar celular de R$ 2500`: adiciona na lista de desejos e analisa quando pode comprar.
- `adiciona PlayStation 5 na lista de desejos`: tenta estimar o preco, salva o item e devolve decisao, melhor caminho, prazo e forma de pagamento recomendada.
