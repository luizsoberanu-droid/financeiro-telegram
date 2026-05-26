# Aurum Capital v2.2

Analista patrimonial pessoal com **Inteligência Artificial REAL**, **alertas automáticos**, **PWA para celular** e **relatórios PDF**.
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
| `checkup do analista` | Envia saldo, dividas, limite do cartao, desejos priorizados e proximas acoes |
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
aurum-capital/
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



## Aurum Capital v6 — Disciplina pesada + backup completo

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


## Aurum Capital v7 — Cartao alimentacao + Cofre vitalicio

Novidades desta melhoria:
- Saldo do cartao alimentacao no dashboard principal.
- Aba dedicada para configurar saldo, recarga mensal e dia de recarga.
- Registro de uso, recarga e ajuste do cartao alimentacao sem baguncar o saldo em dinheiro.
- No Telegram conversacional, pergunte sobre saldo do cartao alimentacao ou salvamento para a IA consultar e orientar.
- Aba `Cofre` no painel com tres camadas:
  - Postgres persistente no Render para uso real em producao.
  - SQLite para uso local/teste.
  - Google Sheets como espelho permanente.
  - Snapshot JSON portatil para guardar fora do app.
- Autosave de apontamentos: cada operacao importante `POST/PUT/DELETE` vira um registro na tabela `apontamentos`, com origem, entidade, resumo e data.

Novos endpoints:
- `GET /api/saldo/utilizacao`
- `GET /api/mercado/analise`
- `GET /api/alimentacao`
- `POST /api/alimentacao/config`
- `POST /api/alimentacao/movimento`
- `GET /api/salvamento/status`
- `GET /api/persistencia/status`
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


## Aurum Capital v8 — Telegram como analista patrimonial

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
- `quanto posso usar do saldo?`: informa se pode usar mais, quanto ainda esta liberado com seguranca ou quanto precisa reduzir.
- `onde investir meu dinheiro agora?`: cruza renda, dividas, reserva, saldo livre, renda fixa, bancos, ETFs e acoes para montar uma lista de estudo com controle de risco.
- `quero comprar celular de R$ 2500`: adiciona na lista de desejos e analisa quando pode comprar.
- `posso comprar celular de R$ 2500 em 10x?`: usa a Central de Decisao para dizer se compra, espera, parcela ou compra a vista.
- `adiciona PlayStation 5 na lista de desejos`: busca media real de preco na internet, salva o item e devolve decisao, melhor caminho, prazo e forma de pagamento recomendada.
- `fechamento do mes`: salva o resumo mensal, compara com o mes anterior e devolve proximas acoes.
- `radar de desejos`: mostra quedas de preco e itens que ficaram mais seguros para comprar.
- Revisao mensal: quando as automacoes Telegram estao ligadas, o Aurum Capital consulta a media dos desejos todo mes, guarda historico e avisa se o preco cair ou se a compra ficar segura.
- Check-up sazonal: o Aurum Capital cruza estacao do ano e clima para sugerir itens como roupas de frio, roupas leves, cobertor ou ventilador antes da necessidade apertar.
- Check-up do analista: quando `TELEGRAM_AUTOMATIONS_ENABLED=true`, o Aurum envia todo dia uma leitura com risco do mes, saldo, dividas, limite seguro de credito, desejos ordenados por prioridade e proximas acoes.
- Para receber mensagens automaticas, use `TELEGRAM_AUTOMATIONS_ENABLED=true`. Se quiser fixar um chat, use `TELEGRAM_DEFAULT_CHAT_ID`.
- Para acordar o Render Free e receber check-up mesmo apos sono, configure um cron externo/UptimeRobot chamando `GET /api/analista/checkup?enviar_telegram=true`.

## Render Free - modo economico de memoria

O deploy foi ajustado para rodar com menos memoria no Render:
- `WEB_CONCURRENCY=1` e `GUNICORN_THREADS=2` por padrao no Docker.
- Cron interno fica desligado por padrao. Para ligar, use `AURUM_ENABLE_INTERNAL_CRON=true`.
- Backup completo no Google Sheets depois de toda alteracao fica desligado por padrao. Para ligar, use `GOOGLE_SHEETS_BACKUP_EVERY_MUTATION=true`.
- O backup manual continua disponivel pelo painel/endpoint de salvamento.
- A geracao de PDF carrega `reportlab` somente quando alguem pede relatorio.

Configuracao recomendada no Render Free:
- Manter `AURUM_ENABLE_INTERNAL_CRON=false`.
- Usar UptimeRobot/cron externo para chamar `/api/analista/checkup?enviar_telegram=true`.
- Manter backup automatico por mutacao desligado e usar `Salvar agora no Google Sheets` apos mudancas importantes.

## Render com banco persistente

Para a IA lembrar do historico mensal, conversas, desejos, limites e lancamentos mesmo se o Render reiniciar, configure um banco persistente:

1. Crie um banco PostgreSQL no Render.
2. Copie a Internal Database URL do banco.
3. No Web Service do Aurum Capital, adicione a variavel:
   - `DATABASE_URL=postgresql://...`
4. Opcionalmente mantenha o pool pequeno para economizar memoria:
   - `DB_POOL_SIZE=2`
   - `DB_MAX_OVERFLOW=2`
   - `DB_POOL_RECYCLE=1800`
5. Refaca o deploy.

Depois do deploy, abra `Cofre` no painel. O bloco `Persistencia` deve aparecer como `PERSISTENTE`.

Configuracao recomendada de seguranca de dados:
- `DATABASE_URL`: fonte principal do historico vitalicio.
- `GOOGLE_SHEETS_ID` e `GOOGLE_SERVICE_ACCOUNT_JSON`: espelho externo para backup/restauracao.
- `GOOGLE_SHEETS_RESTORE_ON_START=true`: restaura automaticamente se o banco parecer novo.
- `GOOGLE_SHEETS_BACKUP_EVERY_MUTATION=false`: economiza memoria no Render; use backup manual ou cron externo.
- `AURUM_ENABLE_INTERNAL_CRON=false`: evita consumo extra no web worker.
- `TELEGRAM_AUTOMATIONS_ENABLED=true`: permite check-ups, alertas e revisoes automaticas quando um cron externo chama os endpoints.

Endpoints uteis para monitoramento externo:
- `GET /api/ping`
- `GET /api/persistencia/status`
- `GET /api/analista/checkup?enviar_telegram=true`
- `GET /api/analista/fechamento_mensal?enviar_telegram=true`
- `GET /api/desejos/radar`
- `POST /api/decisao/compra`
- `POST /api/salvamento/google_sheets`

## Aurum Capital v9 — Interacoes de analista financeiro

Novidades:
- Pendencias de conversa no Telegram agora ficam salvas no banco em `interacoes_pendentes`.
- Se voce disser `comprei lanche 25`, a IA pergunta a forma de pagamento e salva a resposta mesmo se o worker reiniciar entre uma mensagem e outra.
- Central de Decisao no painel de desejos para simular compra, valor, parcelas e opcao de salvar na lista.
- Endpoint `/api/decisao/compra` para decidir compra por API/Telegram.
- Endpoint `/api/analista/fechamento_mensal` para fechamento mensal com comparativo.
- Endpoint `/api/desejos/radar` para oportunidades da lista de desejos.
- A IA ganhou ferramentas internas para fechamento mensal, radar de desejos e decisao de compra.

## Aurum Capital v10 - Plano de Conquista

Novidades:
- A IA agora monta um plano detalhado para metas grandes, como `quero comprar uma casa de R$ 600000 em 10 anos`.
- O plano separa o dinheiro em ordem: recompor saldo, quitar dividas, reserva de emergencia, roupas/necessidades, veiculo/manutencao, entrada/documentos e so depois casa.
- A resposta mostra o valor exato da fundacao financeira, entrada + documentos, total antes de assumir a casa, aporte mensal necessario, gap mensal e parcela habitacional segura hoje.
- O painel `Plano de Prosperidade` ganhou o bloco `Plano de Conquista`, com escada de prioridade, plano mensal e caminhos possiveis: financiamento, carta de credito/consorcio ou compra a vista.
- O Telegram usa esse plano quando voce pergunta por casa, patrimonio, milhao ou meta grande.

Endpoint:
- `GET /api/metas/conquista?valor_meta=600000&prazo_anos=10`

## Aurum Capital v11 - Plano de compra na lista de desejos

Novidades:
- Cada desejo pode guardar urgencia, motivo, prazo opcional e plano de acao.
- Exemplo no Telegram: `adiciona geladeira de R$ 2500 urgente na lista de desejos`.
- A IA nao usa urgencia como autorizacao automatica: se houver saldo negativo, divida ativa ou reserva fraca, ela trava a compra e monta plano para recuperar caixa, quitar dividas e guardar dinheiro antes.
- A ordenacao respeita prioridade real: geladeira, fogao, saude, roupa basica e trabalho ficam acima de iPhone, lazer e status; urgencia so desempata itens do mesmo nivel.
- O painel de desejos mostra urgencia, forma recomendada, parcelamento planejado e botao `Plano IA`.

Endpoints:
- `POST /api/desejo`
- `POST /api/desejos/plano_compra`
- `POST /api/decisao/compra`
