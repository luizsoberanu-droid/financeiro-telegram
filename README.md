# 🚀 NEXUS AI v2.0

Assistente financeiro pessoal com **Inteligência Artificial REAL** usando Function Calling.
100% gratuito, 100% open source.

---

## ✨ O QUE MUDOU (v1 → v2)

| Recurso | v1 (Antigo) | v2 (Novo) |
|---------|------------|-----------|
| **IA** | Regras hardcoded (if/elif) | LLM real (Groq/Google) com Function Calling |
| **Banco de Dados** | JSON em memória (perdia dados) | SQLite persistente |
| **Memória** | Apenas wizard | Histórico completo de conversas |
| **Alertas** | Zero | Proativos automáticos |
| **Arquitetura** | 1 arquivo monolito | Módulos separados |
| **Personalização** | Zero | Baseada em histórico e contexto |
| **Simulações** | Básico | Cenários complexos com IA |
| **Escalabilidade** | 1 usuário | Multi-tenant |

---

## 🆓 100% GRATUITO - APIs Utilizadas

### Opção 1: Groq (Recomendado)
- **Site:** https://console.groq.com
- **Custo:** R$ 0 (sem cartão de crédito)
- **Limites:** 30 RPM, 14.400 req/dia (modelo 8B) ou 1.000 req/dia (70B)
- **Modelos:** Llama 3.3 70B, Llama 4 Scout, Qwen3, Kimi K2

### Opção 2: Google AI Studio
- **Site:** https://aistudio.google.com
- **Custo:** R$ 0 (sem cartão de crédito)
- **Limites:** 15 RPM, 1.500 req/dia
- **Modelos:** Gemini 2.5 Flash, Gemini 2.5 Pro

### Fallback (sem API key)
O sistema funciona mesmo sem API key, usando regras básicas. Mas a experiência com IA é muito superior.

---

## 🚀 Deploy no Render

### 1. Criar novo Web Service
- Conecte seu repositório GitHub
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`

### 2. Variáveis de Ambiente
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx  # ou GOOGLE_API_KEY
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
DATABASE_URL=sqlite:///nexus.db    # opcional, padrão já funciona
```

### 3. Configurar Webhook do Telegram
```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<SEU-APP>.onrender.com/webhooks/telegram
```

---

## 🤖 Comandos do Telegram

### Comandos Rápidos (sem IA)
| Comando | Descrição |
|---------|-----------|
| `status` | Situação financeira atual |
| `contas` | Lista de contas fixas |
| `dividas` | Análise de dívidas |
| `reserva` | Status da reserva de emergência |
| `plano` | Plano mensal completo |
| `alertas` | Verificar alertas pendentes |
| `pagar [nome]` | Marcar conta como paga |
| `extra [valor]` | Registrar renda extra |
| `[desc] [valor]` | Lançar gasto rápido |

### IA Avançada (qualquer texto)
- *"Posso gastar 200 num jantar hoje?"*
- *"Como faço para sair da dívida?"*
- *"Quando posso começar a investir?"*
- *"Me dá um resumo do mês"*
- *"Qual minha próxima conta a vencer?"*

A IA consulta seus dados reais e dá respostas contextualizadas!

---

## 🏗️ Arquitetura

```
nexus-ai/
├── app.py                 # Entry point Flask
├── requirements.txt       # Dependências
├── models/
│   └── database.py        # SQLAlchemy + SQLite
├── services/
│   ├── ai_service.py      # LLM + Function Calling
│   ├── finance_service.py # Lógica financeira
│   └── alert_service.py   # Alertas proativos
├── routes/
│   ├── api.py             # Rotas REST
│   └── telegram.py        # Webhook Telegram
├── utils/
│   └── helpers.py         # Funções utilitárias
└── templates/
    └── dashboard.html     # Painel web
```

---

## 🧪 Testar Local

```bash
# 1. Clonar e entrar
pip install -r requirements.txt

# 2. Configurar variáveis (opcional)
export GROQ_API_KEY="sua-key-aqui"
export TELEGRAM_BOT_TOKEN="seu-token-aqui"

# 3. Rodar
python app.py

# 4. Acessar
http://localhost:5000
```

---

## 🎯 Roadmap Futuro (também gratuito)

- [ ] Machine Learning local (scikit-learn) para previsão de gastos
- [ ] Gráficos interativos no dashboard
- [ ] Exportação para Excel/PDF
- [ ] Múltiplos usuários (multi-tenant)
- [ ] Integração com Open Banking (quando disponível no Brasil)
- [ ] App mobile (PWA)

---

## 📄 Licença

MIT License - Use, modifique e distribua livremente.

**Feito com ❤️ para quem quer controlar as finanças sem pagar nada.**
