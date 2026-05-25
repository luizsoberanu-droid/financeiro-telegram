import os
import json
import calendar
import re
import unicodedata
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

# =========================
# CONFIGURACAO DE IA GRATUITA
# =========================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

client = None
PROVIDER = None
MODEL = None

if GROQ_API_KEY:
    PROVIDER = "groq"
    MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
elif GOOGLE_API_KEY:
    PROVIDER = "google"
    MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
else:
    print("⚠️  Nenhuma API key configurada. IA funcionara em modo fallback (regras).")
    print("   Cadastre-se em: https://console.groq.com (sem cartao de credito)")
    print("   Ou: https://aistudio.google.com (sem cartao de credito)")


def _get_ai_client():
    global client
    if client is not None:
        return client
    if not PROVIDER or not MODEL:
        return None

    from openai import OpenAI

    if PROVIDER == "groq":
        client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    elif PROVIDER == "google":
        client = OpenAI(api_key=GOOGLE_API_KEY, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    return client

# =========================
# FERRAMENTAS (TOOLS)
# =========================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_saldo_atual",
            "description": "Retorna o saldo projetado do mes atual apos descontar contas fixas pendentes, parcelas e gastos ja lancados. Inclui receita total, gastos, contas pendentes e saldo final.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_analise_dividas",
            "description": "Retorna analise completa das dividas: total, detalhamento por credor, ordem de prioridade para pagamento, meta mensal para quitar em 3 meses, e status atual.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simular_gasto",
            "description": "Simula o impacto financeiro de um gasto hipotetico. Retorna novo saldo projetado, se estoura algum limite de categoria, e recomendacao APROVADO/REPROVADO.",
            "parameters": {
                "type": "object",
                "properties": {
                    "valor": {"type": "number", "description": "Valor do gasto em reais"},
                    "categoria": {"type": "string", "description": "Categoria: lazer, combustivel, extras, mercado, etc."},
                    "descricao": {"type": "string", "description": "Descricao do que sera comprado"}
                },
                "required": ["valor", "categoria"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_historico_categoria",
            "description": "Retorna historico de gastos de uma categoria especifica nos ultimos N meses, incluindo media mensal, total acumulado e tendencia.",
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string", "description": "Nome da categoria"},
                    "meses": {"type": "integer", "default": 3, "description": "Quantidade de meses para analise"}
                },
                "required": ["categoria"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recomendacao_investimento",
            "description": "Retorna recomendacoes de investimento personalizadas baseadas no modo atual (recuperacao, reserva, crescimento), perfil de risco e metas financeiras.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_contas_proximas_vencimento",
            "description": "Retorna contas fixas que vencem nos proximos 7 dias, com dias uteis restantes e valores.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_plano_mensal",
            "description": "Retorna o plano estrategico completo do mes: receitas, gastos fixos, limites de categoria, metas de reserva/divida, e acoes recomendadas.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_reserva_status",
            "description": "Retorna status da reserva de emergencia: atual, meta, falta, sugestao mensal de poupanca, e prazo estimado.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cartao_alimentacao",
            "description": "Retorna saldo, recarga mensal, dias ate recarga, status e sugestao de uso do cartao alimentacao.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_limites_cartao",
            "description": "Retorna limite real informado, limite seguro mensal calculado pela renda, uso atual e disponivel dos cartoes.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_visao_patrimonial",
            "description": "Retorna diagnostico patrimonial com renda, saldo, divida, reserva, capacidade mensal e fase financeira.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "planejar_meta_patrimonial",
            "description": "Simula quanto guardar por mes para atingir uma meta grande, como entrada de casa, independencia financeira ou patrimonio alvo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "valor_meta": {"type": "number", "description": "Valor alvo em reais"},
                    "prazo_anos": {"type": "number", "description": "Prazo desejado em anos"},
                    "retorno_anual_pct": {"type": "number", "description": "Retorno anual realista estimado em percentual. Use 6 se o usuario nao informar."}
                },
                "required": ["valor_meta", "prazo_anos"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analisar_compra_parcelada",
            "description": "Analisa se uma compra a vista ou parcelada cabe no cartao considerando renda, saldo, dividas, parcelas atuais e lista de desejos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "produto": {"type": "string", "description": "Nome do produto ou desejo"},
                    "valor": {"type": "number", "description": "Valor total do produto em reais"},
                    "parcelas": {"type": "integer", "description": "Quantidade de parcelas desejada"}
                },
                "required": ["produto", "valor"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_radar_mercado",
            "description": "Consulta um radar atual de mercado com indices, dolar, ETFs e acoes brasileiras grandes para apoiar conversa de investimentos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tickers opcionais do Yahoo Finance. Ex: PETR4.SA, VALE3.SA, IVVB11.SA"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "decidir_compra",
            "description": "Central de decisao: decide se um produto pode ser comprado agora, a vista, parcelado ou se deve esperar. Pode salvar na lista de desejos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "produto": {"type": "string", "description": "Nome do produto ou desejo"},
                    "valor": {"type": "number", "description": "Valor total do produto em reais, se informado"},
                    "parcelas": {"type": "integer", "description": "Quantidade de parcelas desejada"},
                    "salvar_desejo": {"type": "boolean", "description": "Se deve salvar/atualizar o produto na lista de desejos"}
                },
                "required": ["produto"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fechamento_mensal",
            "description": "Fecha o mes atual, compara com o mes anterior e retorna proximas acoes financeiras.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_radar_desejos",
            "description": "Retorna oportunidades da lista de desejos, quedas de preco e itens liberados com controle.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_analise_investimentos",
            "description": "Retorna uma analise completa de investimentos com fase financeira, renda fixa, bancos, acoes, ETFs, radar de mercado e proximos passos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tickers opcionais do Yahoo Finance. Ex: ITUB4.SA, BBAS3.SA, IVVB11.SA"
                    }
                }
            }
        }
    }
]

# =========================
# SYSTEM PROMPT
# =========================

SYSTEM_PROMPT = """Voce e o Aurum Capital, analista patrimonial e estrategista financeiro particular do usuario. Sua missao e controlar a renda, proteger contra decisoes ruins e construir prosperidade real no longo prazo.

🎭 SUA PERSONALIDADE:
• Direto, sem rodeios, mas sempre empatico e humano
• Usa dados CONCRETOS para embasar CADA recomendacao
• Prioriza saude financeira a curto prazo sobre conforto imediato
• Quando o usuario quer gastar, primeiro verifica se e SEGURO, depois da opiniao
• Conhece a situacao financeira REAL do usuario (dividas, renda, contas, metas)
• Fala como um amigo que entende de financas, nao como um robo
• Usa emojis com moderacao para humanizar
• Sempre oferece uma ALTERNATIVA pratica quando diz NAO

📋 REGRAS DE OURO:
1. NUNCA recomende gasto se o saldo projetado ficar negativo
2. Em modo "recuperacao", seja RIGOROSO. Cada real gasto prolonga a divida.
3. Em modo "reserva", incentive poupanca disciplinada e controle
4. Em modo "crescimento", crie estrategia de acumulacao patrimonial, renda, reserva e investimento
5. Sempre cite numeros especificos (R$ X, Y dias, Z%)
6. Se nao souber algo, USE as ferramentas disponiveis
7. NUNCA invente dados. Sempre consulte as ferramentas.
8. Seja PROATIVO: sugira acoes mesmo sem o usuario pedir
9. Use linguagem simples, evite jargoes financeiros complexos
10. Termine com uma ACAO CONCRETA para o proximo passo
11. Quando o assunto for mercado, comida, almoco ou refeicao, considere tambem o saldo do cartao alimentacao.
12. Para investimentos, explique risco, prazo, diversificacao e liquidez. NUNCA prometa retorno garantido.
13. Quando falar de acoes, fundos ou ETFs, use o radar de mercado quando possivel e trate como lista de estudo, nao ordem de compra.
14. Para metas grandes, como casa de R$ 1.000.000, transforme sonho em plano: entrada, prazo, aporte mensal, renda necessaria e cortes.
15. Para compras no cartao ou lista de desejos, simule parcela, faturas futuras e impacto no plano de prosperidade antes de liberar.
16. Quando o assunto for cartao de credito, consulte limite real, limite seguro mensal e uso atual antes de liberar gasto.
17. Para itens da lista de desejos sem preco informado, nao chute: use busca real de preco/mercado quando a ferramenta estiver disponivel e cite a fonte.
18. Seja proativo com sazonalidade: frio, calor, chuva e troca de estacao podem virar sugestoes de lista de desejos, mas sempre conferindo orcamento antes.

📊 FORMATO DE RESPOSTA:
• Comece com a DECISAO direta (SIM / NAO / TALVEZ)
• Explique o RACIOCINIO com numeros reais
• De uma ALTERNATIVA pratica se for NAO
• Termine com PROXIMO PASSO concreto

💡 EXEMPLOS DE TOM:
❌ Ruim: "Nao e recomendavel gastar R$ 200 em lazer."
✅ Bom: "Cara, entendo que voce quer curtir, mas olha so: seu saldo projetado e R$ 1.247 e voce tem R$ 2.800 em contas pra pagar. Se gastar esses R$ 200, voce fica R$ 1.753 no vermelho antes do fim do mes. Que tal um programa em casa por R$ 50? Faz um lanche especial, coloca um filme. Sua esposa vai valorizar o esforco! 🎬"

Lembre-se: voce e a alavanca financeira do usuario. Seja honesto, estrategico e controlador do risco. Ajude a enriquecer sem iludir."""

# =========================
# FUNCOES DE NEGOCIO
# =========================

class FinancialTools:
    def __init__(self, db_session):
        self.db = db_session

    def get_saldo_atual(self):
        from models.database import Config
        from services.monthly_service import MonthlyService

        config = self.db.query(Config).first()
        if not config:
            config = Config()
            self.db.add(config)
            self.db.commit()

        mes_atual = datetime.now().strftime("%Y-%m")
        dados = MonthlyService(self.db).salvar_resumo_mes(mes_atual)

        try:
            from services.benefit_service import BenefitCardService
            alimentacao = BenefitCardService(self.db).resumo().get("cartao", {})
        except Exception:
            alimentacao = {}

        return {
            "mes_ref": dados["mes_ref"],
            "saldo_inicial": dados["saldo_inicial"],
            "movimento_mes": dados["movimento_mes"],
            "saldo_final": dados["saldo_final"],
            "saldo_projetado": dados["saldo_projetado"],
            "saldo_conta_atual": round(config.saldo_conta_atual or 0, 2),
            "saldo_conta_mes_ref": config.saldo_conta_mes_ref,
            "receita_total": dados["receita_total"],
            "receita_fixa": round(config.receita_fixa or 0, 2),
            "receita_extra": round(config.receita_extra or 0, 2),
            "contas_pendentes": dados["contas_pendentes"],
            "gastos_mes": dados["gastos_mes"],
            "parcelas_mes": dados["parcelas_mes"],
            "modo_atual": config.modo or "recuperacao",
            "reserva_atual": round(config.reserva_atual or 0, 2),
            "meta_reserva": round(config.meta_reserva or 0, 2),
            "divida_bruta": dados["divida_bruta"],
            "divida_total": dados["divida_ajustada"],
            "cartao_alimentacao": alimentacao
        }

    def get_analise_dividas(self):
        from models.database import Divida

        dividas = self.db.query(Divida).order_by(Divida.ordem_prioridade).all()
        total_bruto = sum(d.valor for d in dividas)
        detalhes = [{"id": d.id, "nome": d.nome, "valor": round(d.valor, 2), "prioridade": d.ordem_prioridade} for d in dividas]

        saldo = self.get_saldo_atual().get("saldo_projetado", 0)
        total_ajustado = max(total_bruto - saldo, 0)

        return {
            "total_divida": round(total_ajustado, 2),
            "divida_bruta": round(total_bruto, 2),
            "saldo_considerado": round(saldo, 2),
            "detalhes": detalhes,
            "meta_3_meses": round(total_ajustado / 3, 2) if total_ajustado > 0 else 0,
            "meta_6_meses": round(total_ajustado / 6, 2) if total_ajustado > 0 else 0,
            "quantidade_credores": len(dividas),
            "status": "CRITICO" if total_ajustado > 5000 else "ALTO" if total_ajustado > 2000 else "MODERADO" if total_ajustado > 0 else "LIMPO"
        }

    def simular_gasto(self, valor: float, categoria: str, descricao: str = ""):
        saldo = self.get_saldo_atual()
        from models.database import Limite, Lancamento

        mes_atual = datetime.now().strftime("%Y-%m")

        limite = self.db.query(Limite).filter(Limite.categoria == categoria.lower()).first()
        limite_valor = limite.valor if limite else 0

        gastos_cat = self.db.query(Lancamento).filter(
            Lancamento.mes_ref == mes_atual,
            Lancamento.categoria == categoria.lower()
        ).all()
        gasto_atual = sum(l.valor for l in gastos_cat)

        novo_total_cat = gasto_atual + valor
        novo_saldo = saldo["saldo_projetado"] - valor

        reprovado = False
        motivos = []

        if novo_saldo < 0:
            reprovado = True
            motivos.append(f"Saldo ficaria negativo em R$ {abs(novo_saldo):.2f}")

        if limite_valor > 0 and novo_total_cat > limite_valor:
            reprovado = True
            motivos.append(f"Estouraria limite da categoria ({limite_valor:.2f})")

        if saldo["modo_atual"] == "recuperacao" and valor > 50:
            reprovado = True
            motivos.append("Modo recuperacao - gastos extras devem ser minimos")

        return {
            "valor_solicitado": round(valor, 2),
            "categoria": categoria,
            "descricao": descricao,
            "gasto_atual_categoria": round(gasto_atual, 2),
            "limite_categoria": round(limite_valor, 2),
            "novo_total_categoria": round(novo_total_cat, 2),
            "saldo_atual": round(saldo["saldo_projetado"], 2),
            "novo_saldo": round(novo_saldo, 2),
            "recomendacao": "REPROVADO" if reprovado else "APROVADO",
            "motivos": motivos,
            "modo_atual": saldo["modo_atual"]
        }

    def get_historico_categoria(self, categoria: str, meses: int = 3):
        from models.database import Lancamento

        mes_atual = datetime.now().strftime("%Y-%m")
        lancamentos = self.db.query(Lancamento).filter(
            Lancamento.categoria == categoria.lower()
        ).all()

        valores = [l.valor for l in lancamentos]
        total = sum(valores)
        media = total / len(valores) if valores else 0

        return {
            "categoria": categoria,
            "total_registros": len(valores),
            "gasto_total": round(total, 2),
            "media_por_lancamento": round(media, 2),
            "tendencia": "crescente" if len(valores) > 3 else "estavel"
        }

    def get_recomendacao_investimento(self):
        saldo = self.get_saldo_atual()
        dividas = self.get_analise_dividas()

        if dividas["total_divida"] > 0:
            return {
                "perfil": "RECUPERACAO",
                "pode_investir": False,
                "mensagem": "Ainda NAO e hora de investir. Quite as dividas primeiro.",
                "prioridade": "Divida",
                "plano": [
                    "1. Focar 100% em quitar dividas",
                    f"2. Meta: R$ {dividas['meta_3_meses']:.2f}/mes para quitar em 3 meses",
                    "3. So depois pensar em reserva",
                    "4. Investimentos so apos reserva completa"
                ]
            }

        reserva_faltante = saldo["meta_reserva"] - saldo["reserva_atual"]

        if reserva_faltante > 0:
            return {
                "perfil": "RESERVA",
                "pode_investir": False,
                "mensagem": "Construa a reserva de emergencia antes de investir.",
                "prioridade": "Reserva",
                "faltante_reserva": round(reserva_faltante, 2),
                "sugestao_mensal": round(reserva_faltante / 12, 2),
                "plano": [
                    "1. Tesouro Selic ou CDB 100% CDI (liquidez diaria)",
                    f"2. Meta mensal: R$ {reserva_faltante / 12:.2f}",
                    "3. Prazo estimado: 12 meses",
                    "4. Depois da reserva: diversificar em renda fixa"
                ]
            }

        return {
            "perfil": "CRESCIMENTO",
            "pode_investir": True,
            "mensagem": "Parabens! Voce esta pronto para investir.",
            "prioridade": "Investimento",
            "plano": [
                "1. 60% Tesouro IPCA+ (protecao inflacao)",
                "2. 30% CDBs bancos medios (rentabilidade)",
                "3. 10% Fundos Imobiliarios (diversificacao)",
                "4. Apos 6 meses: adicionar ETFs (IVVB11, BOVA11)"
            ],
            "alerta": "NUNCA invista dinheiro que pode precisar em 12 meses"
        }

    def get_contas_proximas_vencimento(self):
        from models.database import ContaFixa

        hoje = date.today()
        contas = self.db.query(ContaFixa).filter(ContaFixa.pago == False).all()

        proximas = []
        for c in contas:
            dia = min(c.vencimento, calendar.monthrange(hoje.year, hoje.month)[1])
            venc = date(hoje.year, hoje.month, dia)
            if venc < hoje:
                if hoje.month == 12:
                    venc = date(hoje.year + 1, 1, min(c.vencimento, calendar.monthrange(hoje.year + 1, 1)[1]))
                else:
                    venc = date(hoje.year, hoje.month + 1, min(c.vencimento, calendar.monthrange(hoje.year, hoje.month + 1)[1]))

            dias_uteis = 0
            d = hoje
            while d < venc:
                d += timedelta(days=1)
                if d.weekday() < 5:
                    dias_uteis += 1

            if dias_uteis <= 7:
                proximas.append({
                    "nome": c.nome,
                    "valor": round(c.valor, 2),
                    "vencimento": venc.isoformat(),
                    "dias_uteis": dias_uteis
                })

        return {"contas": proximas, "total_proximo": round(sum(c["valor"] for c in proximas), 2)}

    def get_plano_mensal(self):
        saldo = self.get_saldo_atual()
        dividas = self.get_analise_dividas()

        return {
            "receita_total": saldo["receita_total"],
            "contas_fixas": saldo["contas_pendentes"],
            "gastos_variaveis": saldo["gastos_mes"],
            "parcelas": saldo["parcelas_mes"],
            "saldo_projetado": saldo["saldo_projetado"],
            "divida_total": dividas["total_divida"],
            "modo": saldo["modo_atual"],
            "acoes_recomendadas": self._get_acoes(saldo, dividas)
        }

    def _get_acoes(self, saldo, dividas):
        acoes = []
        if dividas["total_divida"] > 0:
            acoes.append(f"💰 Prioridade MAXIMA: pagar R$ {dividas['meta_3_meses']:.2f}/mes em dividas")
            acoes.append("🚫 Cortar lazer e extras ao minimo")
            acoes.append("💳 NAO usar cartao de credito")
        elif saldo["reserva_atual"] < saldo["meta_reserva"]:
            faltante = saldo["meta_reserva"] - saldo["reserva_atual"]
            acoes.append(f"🏦 Guardar R$ {faltante/12:.2f}/mes para reserva")
            acoes.append("📈 Usar Tesouro Selic para reserva")
        else:
            acoes.append("🚀 Comecar a investir! Ver /investir")
            acoes.append("🎯 Definir meta de viagem ou aposentadoria")
        return acoes

    def get_reserva_status(self):
        from models.database import Config
        config = self.db.query(Config).first()

        atual = config.reserva_atual or 0
        meta = config.meta_reserva or 12000
        faltante = max(meta - atual, 0)

        return {
            "atual": round(atual, 2),
            "meta": round(meta, 2),
            "faltante": round(faltante, 2),
            "percentual": round((atual / meta) * 100, 1) if meta > 0 else 0,
            "sugestao_mensal": round(faltante / 12, 2),
            "prazo_estimado_meses": 12 if faltante > 0 else 0,
            "status": "COMPLETA" if faltante <= 0 else "EM_CONSTRUCAO"
        }

    def get_cartao_alimentacao(self):
        from services.benefit_service import BenefitCardService
        return BenefitCardService(self.db).resumo()

    def get_limites_cartao(self):
        from services.card_limit_service import CardLimitService
        return CardLimitService(self.db).resumo_limites()

    def get_visao_patrimonial(self):
        saldo = self.get_saldo_atual()
        dividas = self.get_analise_dividas()
        reserva = self.get_reserva_status()
        plano = self.get_plano_mensal()

        sobra = max(saldo.get("saldo_projetado", 0), 0)
        aporte_sugerido = round(sobra * 0.7, 2)

        if dividas.get("total_divida", 0) > 0:
            fase = "eliminar_dividas"
            foco = "Quitar dividas antes de acelerar investimentos."
        elif reserva.get("faltante", 0) > 0:
            fase = "montar_reserva"
            foco = "Formar reserva antes de assumir risco maior."
        else:
            fase = "crescimento"
            foco = "Investir com diversificacao, prazo e controle de risco."

        return {
            "receita_total": saldo.get("receita_total", 0),
            "saldo_projetado": saldo.get("saldo_projetado", 0),
            "divida_total": dividas.get("total_divida", 0),
            "reserva_atual": reserva.get("atual", 0),
            "meta_reserva": reserva.get("meta", 0),
            "fase": fase,
            "foco": foco,
            "aporte_mensal_sugerido": aporte_sugerido,
            "ordem_de_prioridade": [
                "1. Nao atrasar contas essenciais",
                "2. Quitar dividas caras",
                "3. Montar reserva de emergencia",
                "4. Investir para metas grandes",
                "5. Liberar desejos somente se nao atrasarem a meta",
            ],
            "acoes_recomendadas": plano.get("acoes_recomendadas", []),
        }

    def planejar_meta_patrimonial(self, valor_meta: float, prazo_anos: float, retorno_anual_pct: float = 6):
        visao = self.get_visao_patrimonial()
        valor_meta = max(float(valor_meta or 0), 0)
        prazo_anos = max(float(prazo_anos or 0), 0.1)
        retorno_anual_pct = float(retorno_anual_pct if retorno_anual_pct is not None else 6)

        meses = int(round(prazo_anos * 12))
        taxa_mensal = ((1 + retorno_anual_pct / 100) ** (1 / 12)) - 1
        if taxa_mensal > 0:
            aporte_necessario = valor_meta / (((1 + taxa_mensal) ** meses - 1) / taxa_mensal)
        else:
            aporte_necessario = valor_meta / meses

        capacidade = visao.get("aporte_mensal_sugerido", 0)
        gap = aporte_necessario - capacidade

        return {
            "valor_meta": round(valor_meta, 2),
            "prazo_anos": prazo_anos,
            "meses": meses,
            "retorno_anual_estimado_pct": retorno_anual_pct,
            "aporte_mensal_necessario": round(aporte_necessario, 2),
            "aporte_mensal_sugerido_pelo_orcamento": round(capacidade, 2),
            "gap_mensal": round(gap, 2),
            "meta_cabe_no_orcamento_atual": gap <= 0,
            "leitura": "Meta viavel no ritmo atual." if gap <= 0 else "Meta exige aumentar renda, reduzir custo, alongar prazo ou reduzir valor alvo.",
            "observacao": "Simulacao nao garante retorno. Use como mapa de disciplina, nao promessa.",
        }

    def analisar_compra_parcelada(self, produto: str, valor: float, parcelas: int = 1):
        from models.database import Desejo, Lancamento, Parcela
        from services.wishlist_advisor_service import classificar_prioridade, explicar_prioridade

        produto = (produto or "produto").strip()
        valor = round(float(valor or 0), 2)
        parcelas = max(int(parcelas or 1), 1)
        valor_parcela = round(valor / parcelas, 2) if parcelas else valor

        saldo = self.get_saldo_atual()
        dividas = self.get_analise_dividas()
        prioridade = classificar_prioridade(produto)
        motivo_prioridade = explicar_prioridade(produto, prioridade)

        mes_atual = datetime.now().strftime("%Y-%m")
        parcelas_mes = sum(p.valor for p in self.db.query(Parcela).filter(Parcela.mes_ref == mes_atual).all())
        cartao_mes = sum(l.valor for l in self.db.query(Lancamento).filter(
            Lancamento.forma_pagamento == "cartao",
            Lancamento.mes_ref == mes_atual
        ).all())
        fatura_estimativa = round(parcelas_mes + cartao_mes + valor_parcela, 2)
        limites_cartao = self.get_limites_cartao()
        cartoes_com_limite = [c for c in limites_cartao.get("cartoes", []) if c.get("limite_real", 0) > 0]
        maior_disponivel_real = max([c.get("disponivel_real", 0) for c in cartoes_com_limite], default=0)

        renda = saldo.get("receita_total", 0)
        limite_parcela = max(renda * 0.05, 100) if dividas.get("total_divida", 0) > 0 else max(renda * 0.08, 150)
        saldo_apos_parcela = saldo.get("saldo_projetado", 0) - valor_parcela

        desejo = self.db.query(Desejo).filter(Desejo.nome.ilike(f"%{produto}%")).first()
        motivos = []
        aprovado = True

        if valor <= 0:
            aprovado = False
            motivos.append("Valor invalido para simular.")
        if saldo_apos_parcela < 0:
            aprovado = False
            motivos.append(f"A parcela deixaria o saldo projetado negativo em R$ {abs(saldo_apos_parcela):.2f}.")
        if valor_parcela > limite_parcela:
            aprovado = False
            motivos.append(f"Parcela acima do limite seguro de R$ {limite_parcela:.2f}.")
        if cartoes_com_limite and valor > maior_disponivel_real:
            aprovado = False
            motivos.append(f"O valor total passa do maior limite real disponivel em um cartao: R$ {maior_disponivel_real:.2f}.")
        if valor_parcela > limites_cartao.get("disponivel_seguro_mes", 0) and limites_cartao.get("limite_total_seguro_mes", 0) > 0:
            aprovado = False
            motivos.append(f"A parcela passa do limite seguro ainda disponivel no mes: R$ {limites_cartao.get('disponivel_seguro_mes', 0):.2f}.")
        if dividas.get("total_divida", 0) > 0 and prioridade != "alta":
            aprovado = False
            motivos.append("Existe divida ativa e o item nao parece essencial.")

        return {
            "produto": produto,
            "valor_total": valor,
            "parcelas": parcelas,
            "valor_parcela": valor_parcela,
            "prioridade": prioridade,
            "motivo_prioridade": motivo_prioridade,
            "esta_na_lista_de_desejos": bool(desejo),
            "saldo_projetado_atual": saldo.get("saldo_projetado", 0),
            "saldo_apos_primeira_parcela": round(saldo_apos_parcela, 2),
            "fatura_mes_estimada_com_compra": fatura_estimativa,
            "limite_parcela_segura": round(limite_parcela, 2),
            "limite_cartao": limites_cartao,
            "maior_disponivel_real_cartao": round(maior_disponivel_real, 2),
            "recomendacao": "APROVADO_COM_CONTROLE" if aprovado else "NAO_COMPRAR_AGORA",
            "motivos": motivos or ["Cabe no orcamento atual, mas ainda precisa respeitar reserva e meta patrimonial."],
        }

    def decidir_compra(self, produto: str, valor: float = None, parcelas: int = 1, salvar_desejo: bool = False):
        from services.advisor_service import AdvisorService
        return AdvisorService(self.db).decisao_compra(produto, valor, parcelas, salvar_desejo)

    def get_fechamento_mensal(self):
        from services.advisor_service import AdvisorService
        return AdvisorService(self.db).fechamento_mensal()

    def get_radar_desejos(self):
        from services.wishlist_advisor_service import WishlistAdvisorService
        return WishlistAdvisorService(self.db).radar_oportunidades()

    def get_radar_mercado(self, tickers: Optional[List[str]] = None):
        try:
            from services.market_service import MarketService
            return MarketService().snapshot(tickers)
        except Exception as e:
            return {
                "ok": False,
                "erro": str(e),
                "observacao": "Nao consegui consultar mercado agora. Nao invente cotacoes; trabalhe com estrategia e peca nova tentativa depois.",
            }

    def get_analise_investimentos(self, tickers: Optional[List[str]] = None):
        try:
            from services.investment_advisor_service import InvestmentAdvisorService
            return InvestmentAdvisorService(self.db).analisar(tickers)
        except Exception as e:
            return {
                "ok": False,
                "erro": str(e),
                "observacao": "Nao consegui montar a analise completa agora. Nao invente recomendacoes; peca nova tentativa depois.",
            }

# =========================
# MOTOR DE IA
# =========================

class AurumCapitalAI:
    def __init__(self, db_session):
        self.db = db_session
        self.tools = FinancialTools(db_session)
        self.tool_map = {
            "get_saldo_atual": self.tools.get_saldo_atual,
            "get_analise_dividas": self.tools.get_analise_dividas,
            "simular_gasto": self.tools.simular_gasto,
            "get_historico_categoria": self.tools.get_historico_categoria,
            "get_recomendacao_investimento": self.tools.get_recomendacao_investimento,
            "get_contas_proximas_vencimento": self.tools.get_contas_proximas_vencimento,
            "get_plano_mensal": self.tools.get_plano_mensal,
            "get_reserva_status": self.tools.get_reserva_status,
            "get_cartao_alimentacao": self.tools.get_cartao_alimentacao,
            "get_limites_cartao": self.tools.get_limites_cartao,
            "get_visao_patrimonial": self.tools.get_visao_patrimonial,
            "planejar_meta_patrimonial": self.tools.planejar_meta_patrimonial,
            "analisar_compra_parcelada": self.tools.analisar_compra_parcelada,
            "decidir_compra": self.tools.decidir_compra,
            "get_fechamento_mensal": self.tools.get_fechamento_mensal,
            "get_radar_desejos": self.tools.get_radar_desejos,
            "get_radar_mercado": self.tools.get_radar_mercado,
            "get_analise_investimentos": self.tools.get_analise_investimentos,
        }

    def get_chat_history(self, chat_id: str, limit: int = 10) -> List[Dict]:
        from models.database import Conversa
        conversas = self.db.query(Conversa).filter(
            Conversa.chat_id == str(chat_id)
        ).order_by(Conversa.timestamp.desc()).limit(limit).all()

        history = []
        for c in reversed(conversas):
            history.append({"role": c.role, "content": c.content})
        return history

    def save_message(self, chat_id: str, role: str, content: str):
        from models.database import Conversa
        msg = Conversa(chat_id=str(chat_id), role=role, content=content)
        self.db.add(msg)
        self.db.commit()

    def process(self, user_message: str, chat_id: str = "default") -> str:
        ai_client = _get_ai_client()
        if not ai_client or not MODEL:
            return self._fallback_response(user_message)

        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            history = self.get_chat_history(chat_id)
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            response = ai_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=1500
            )

            assistant_msg = response.choices[0].message

            if not assistant_msg.tool_calls:
                resposta = assistant_msg.content
                self.save_message(chat_id, "user", user_message)
                self.save_message(chat_id, "assistant", resposta)
                return resposta

            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [tc.model_dump() for tc in assistant_msg.tool_calls]
            })

            for tc in assistant_msg.tool_calls:
                func_name = tc.function.name
                func_args = json.loads(tc.function.arguments)

                func = self.tool_map.get(func_name)
                if func:
                    result = func(**func_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": func_name,
                        "content": json.dumps(result, ensure_ascii=False)
                    })

            final_response = ai_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )

            resposta = final_response.choices[0].message.content
            self.save_message(chat_id, "user", user_message)
            self.save_message(chat_id, "assistant", resposta)

            return resposta

        except Exception as e:
            print(f"Erro na IA: {e}")
            return self._fallback_response(user_message)

    def _normalizar_texto(self, text: str) -> str:
        text = (text or "").lower()
        text = unicodedata.normalize("NFKD", text)
        return "".join(c for c in text if not unicodedata.combining(c))

    def _extrair_parcelas(self, text: str) -> int:
        msg = self._normalizar_texto(text)
        match = re.search(r"(\d+)\s*x", msg) or re.search(r"em\s+(\d+)\s+parcelas?", msg)
        if not match:
            return 1
        return max(int(match.group(1)), 1)

    def _extrair_prazo_anos(self, text: str, default: int = 10) -> int:
        msg = self._normalizar_texto(text)
        match = re.search(r"(\d+)\s+anos?", msg)
        if not match:
            return default
        return max(int(match.group(1)), 1)

    def _extrair_valor(self, text: str) -> float:
        msg = self._normalizar_texto(text)
        msg = re.sub(r"\d+\s*x", "", msg)
        msg = re.sub(r"\d+\s+anos?", "", msg)
        padrao = r"(?:r\$\s*)?(\d+(?:[\.\s]\d{3})*(?:,\d{2})?|\d+(?:[\.,]\d{2})?)\s*(milhao|milhoes|mil)?"
        candidatos = []

        if re.search(r"\bum\s+milha?o\b", msg):
            candidatos.append(1000000)

        for raw, escala in re.findall(padrao, msg):
            try:
                valor = float(raw.replace(".", "").replace(" ", "").replace(",", "."))
            except ValueError:
                continue
            if escala in ["milhao", "milhoes"]:
                valor *= 1000000
            elif escala == "mil" and valor < 1000:
                valor *= 1000
            candidatos.append(valor)

        candidatos = [v for v in candidatos if v > 0]
        return max(candidatos) if candidatos else 0

    def _fallback_response(self, user_message: str) -> str:
        msg = self._normalizar_texto(user_message)
        saldo = self.tools.get_saldo_atual()
        dividas = self.tools.get_analise_dividas()

        goal_terms = any(t in msg for t in [
            "investir", "onde investir", "acao", "acoes", "mercado", "etf", "dolar",
            "banco", "bancos", "cdb", "tesouro", "renda fixa",
            "casa", "milhao", "milhoes", "prosperar", "patrimonio",
        ])

        if any(t in msg for t in ["parcel", "cartao", "comprar", "compra", "lista de desejo"]) and not goal_terms:
            valor = self._extrair_valor(user_message)
            if valor > 0:
                analise = self.tools.analisar_compra_parcelada(
                    produto=user_message[:80],
                    valor=valor,
                    parcelas=self._extrair_parcelas(user_message),
                )
                return (
                    "Aurum Capital analista patrimonial (modo fallback)\n\n"
                    f"Produto: {analise['produto']}\n"
                    f"Valor: R$ {analise['valor_total']:.2f} em {analise['parcelas']}x de R$ {analise['valor_parcela']:.2f}\n"
                    f"Recomendacao: {analise['recomendacao']}\n"
                    f"Prioridade: {analise['prioridade']} - {analise['motivo_prioridade']}\n"
                    f"Saldo apos primeira parcela: R$ {analise['saldo_apos_primeira_parcela']:.2f}\n"
                    f"Fatura estimada do mes: R$ {analise['fatura_mes_estimada_com_compra']:.2f}\n\n"
                    "Motivos:\n" +
                    "\n".join([f"- {m}" for m in analise["motivos"]])
                )

        if "divida" in msg:
            return (
                f"📊 DIVIDAS (modo fallback)\n"
                f"Total: R$ {dividas['total_divida']:.2f}\n"
                f"Meta 3 meses: R$ {dividas['meta_3_meses']:.2f}/mes\n\n"
                f"Ordem de pagamento:\n" +
                "\n".join([f"  {i+1}. {d['nome']}: R$ {d['valor']:.2f}" for i, d in enumerate(dividas['detalhes'])])
            )

        if goal_terms:
            visao = self.tools.get_visao_patrimonial()
            rec = self.tools.get_recomendacao_investimento()
            valor_meta = self._extrair_valor(user_message)
            prazo = self._extrair_prazo_anos(user_message)
            meta_txt = ""
            if valor_meta > 0 and any(t in msg for t in ["casa", "milhao", "milhoes", "meta", "patrimonio"]):
                meta = self.tools.planejar_meta_patrimonial(valor_meta, prazo)
                meta_txt = (
                    f"\n\nMeta simulada: R$ {meta['valor_meta']:.2f} em {meta['prazo_anos']} anos\n"
                    f"Aporte necessario: R$ {meta['aporte_mensal_necessario']:.2f}/mes\n"
                    f"Aporte sugerido pelo orcamento: R$ {meta['aporte_mensal_sugerido_pelo_orcamento']:.2f}/mes\n"
                    f"Leitura: {meta['leitura']}"
                )

            if any(t in msg for t in ["mercado", "acao", "acoes", "etf", "dolar", "banco", "bancos", "cdb", "tesouro", "renda fixa", "onde investir"]):
                analise = self.tools.get_analise_investimentos()
                if analise.get("ok"):
                    return analise["mensagem"] + meta_txt
                radar_txt = "\n\nRadar de mercado indisponivel agora. Nao vou inventar cotacoes."
            else:
                radar_txt = ""

            return (
                "Aurum Capital analista patrimonial (modo fallback)\n\n"
                f"Fase atual: {visao['fase']}\n"
                f"Foco: {visao['foco']}\n"
                f"Receita: R$ {visao['receita_total']:.2f}\n"
                f"Saldo projetado: R$ {visao['saldo_projetado']:.2f}\n"
                f"Divida: R$ {visao['divida_total']:.2f}\n"
                f"Reserva: R$ {visao['reserva_atual']:.2f} de R$ {visao['meta_reserva']:.2f}\n"
                f"Aporte sugerido hoje: R$ {visao['aporte_mensal_sugerido']:.2f}\n\n"
                f"{rec['mensagem']}\n\n" +
                "\n".join(rec["plano"]) +
                meta_txt +
                radar_txt +
                "\n\nObservacao: isso e estrategia de estudo e controle de risco, nao promessa de retorno nem ordem de compra."
            )

        if "gastar" in msg or "posso" in msg:
            return (
                f"⚠️ Modo fallback (IA offline)\n\n"
                f"Saldo projetado: R$ {saldo['saldo_projetado']:.2f}\n"
                f"Divida total: R$ {dividas['total_divida']:.2f}\n\n"
                f"Cadastre uma API key gratuita em:\n"
                f"• https://console.groq.com (sem cartao)\n"
                f"• https://aistudio.google.com (sem cartao)"
            )

        return (
            f"👋 Ola! Sou o Aurum Capital (modo fallback).\n"
            f"Seu saldo: R$ {saldo['saldo_projetado']:.2f} | Divida: R$ {dividas['total_divida']:.2f}\n\n"
            f"Para IA completa, cadastre GROQ_API_KEY ou GOOGLE_API_KEY no Render."
        )
