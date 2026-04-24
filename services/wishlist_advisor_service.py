import re
import requests
from statistics import median

PRIORIDADES = {
    "alta": [
        "geladeira", "fogao", "fogão", "maquina de lavar", "máquina de lavar",
        "cama", "colchao", "colchão", "oculos", "óculos", "remedio", "remédio",
        "consulta", "dentista", "uniforme", "roupa intima", "roupa íntima",
        "calcinha", "cueca", "meia", "sapato trabalho", "notebook trabalho"
    ],
    "media": [
        "celular", "iphone", "notebook", "computador", "monitor", "cadeira",
        "microondas", "micro-ondas", "liquidificador", "air fryer", "bike"
    ],
    "baixa": [
        "videogame", "playstation", "xbox", "tv grande", "viagem", "show",
        "perfume", "relogio", "relógio", "fone premium"
    ],
}

def limpar_query(texto):
    t = (texto or "").lower().strip()
    t = re.sub(r"^(quero comprar|comprar|desejo comprar|analisa compra de|analisar compra de)\s+", "", t)
    t = re.sub(r"\s+(a vista|à vista|parcelado|no cartao|no cartão)$", "", t)
    return t.strip()

def classificar_prioridade(nome):
    n = (nome or "").lower()
    for prioridade, palavras in PRIORIDADES.items():
        if any(p in n for p in palavras):
            return prioridade
    return "media"

def explicar_prioridade(nome, prioridade):
    n = (nome or "").lower()
    if prioridade == "alta":
        if any(p in n for p in ["geladeira", "fogao", "fogão", "maquina", "máquina"]):
            return "é item essencial de casa e impacta sua rotina básica."
        if any(p in n for p in ["calcinha", "cueca", "meia", "roupa intima", "roupa íntima"]):
            return "é item de vestuário básico, então tem prioridade maior que lazer ou luxo."
        return "é item essencial ou de necessidade prática."
    if prioridade == "baixa":
        return "parece ser mais lazer, conforto ou desejo, então deve esperar se houver dívida."
    return "é útil, mas não é mais importante do que contas, dívidas, reserva e itens essenciais."

def buscar_preco_mercado_livre(produto):
    try:
        url = "https://api.mercadolibre.com/sites/MLB/search"
        r = requests.get(url, params={"q": produto, "limit": 10}, timeout=12)
        if not r.ok:
            return {"ok": False, "erro": f"Mercado Livre HTTP {r.status_code}"}
        data = r.json()
        results = data.get("results", [])[:10]
        precos = []
        titulos = []
        for item in results:
            price = item.get("price")
            title = item.get("title")
            if isinstance(price, (int, float)) and price > 0:
                precos.append(float(price))
                if title:
                    titulos.append(title)
        if not precos:
            return {"ok": False, "erro": "sem preços encontrados"}
        return {
            "ok": True,
            "preco_mediano": round(float(median(precos)), 2),
            "preco_medio": round(sum(precos) / len(precos), 2),
            "qtd": len(precos),
            "fonte": "Mercado Livre",
            "exemplo": titulos[0] if titulos else produto
        }
    except Exception as e:
        return {"ok": False, "erro": str(e)}

class WishlistAdvisorService:
    def __init__(self, db_session):
        self.db = db_session

    def _dados_financeiros(self):
        from services.ai_service import FinancialTools
        tools = FinancialTools(self.db)
        return tools.get_saldo_atual(), tools.get_analise_dividas()

    def _faturas_futuras_cartao(self, meses=6):
        from models.database import Parcela, Lancamento
        from datetime import datetime
        atual = datetime.now()
        ano, mes = atual.year, atual.month
        refs = []
        for i in range(meses):
            m = mes + i
            a = ano
            while m > 12:
                m -= 12
                a += 1
            refs.append(f"{a:04d}-{m:02d}")

        total = {ref: 0.0 for ref in refs}

        for p in self.db.query(Parcela).filter(Parcela.mes_ref.in_(refs)).all():
            total[p.mes_ref] = total.get(p.mes_ref, 0) + (p.valor or 0)

        for l in self.db.query(Lancamento).filter(
            Lancamento.forma_pagamento == "cartao",
            Lancamento.mes_ref.in_(refs)
        ).all():
            total[l.mes_ref] = total.get(l.mes_ref, 0) + (l.valor or 0)

        return total

    def analisar_compra(self, produto, preco_informado=None):
        produto = limpar_query(produto)
        prioridade = classificar_prioridade(produto)
        motivo = explicar_prioridade(produto, prioridade)

        preco_info = None
        preco = preco_informado
        if preco is None:
            preco_info = buscar_preco_mercado_livre(produto)
            if preco_info.get("ok"):
                preco = preco_info["preco_mediano"]

        saldo, dividas = self._dados_financeiros()
        saldo_proj = saldo.get("saldo_projetado", 0)
        divida = dividas.get("total_divida", 0)
        renda = saldo.get("receita_total", 0)
        contas = saldo.get("contas_pendentes", 0)
        gastos = saldo.get("gastos_mes", 0)
        parcelas_mes = saldo.get("parcelas_mes", 0)

        faturas = self._faturas_futuras_cartao(6)
        maior_fatura_futura = max(faturas.values()) if faturas else 0

        linhas = []
        linhas.append("🧠 ANÁLISE DE DESEJO — DISCIPLINA PESADA")
        linhas.append("")
        linhas.append(f"Item analisado: {produto}")
        linhas.append(f"Prioridade: {prioridade.upper()} — {motivo}")

        if preco is not None:
            linhas.append(f"Preço usado na análise: R$ {preco:.2f}")
            if preco_info and preco_info.get("ok"):
                linhas.append(f"Fonte: {preco_info['fonte']} — mediana de {preco_info['qtd']} anúncios")
        else:
            linhas.append("Não consegui localizar preço automaticamente. Me envie assim: quero comprar item de 2500")
            preco = 0

        linhas.append("")
        linhas.append("Seu cenário:")
        linhas.append(f"- Receita: R$ {renda:.2f}")
        linhas.append(f"- Contas pendentes: R$ {contas:.2f}")
        linhas.append(f"- Gastos do mês: R$ {gastos:.2f}")
        linhas.append(f"- Parcelas do mês: R$ {parcelas_mes:.2f}")
        linhas.append(f"- Saldo projetado: R$ {saldo_proj:.2f}")
        linhas.append(f"- Dívida ajustada: R$ {divida:.2f}")
        linhas.append(f"- Maior fatura futura já prevista: R$ {maior_fatura_futura:.2f}")
        linhas.append("")

        if preco <= 0:
            linhas.append("Decisão: preciso do valor para simular corretamente.")
            return "\n".join(linhas)

        saldo_apos_avista = saldo_proj - preco

        if saldo_apos_avista >= 0 and divida <= 0 and prioridade == "alta":
            linhas.append("Decisão à vista: TECNICAMENTE POSSÍVEL.")
            linhas.append("Mesmo assim, eu só liberaria se a reserva não for afetada.")
        else:
            linhas.append("Decisão à vista: NÃO recomendo.")
            linhas.append("Sua reserva deve ser usada apenas para imprevistos, não para desejo de compra.")

        limite_parcela_segura = max(renda * 0.05, 100) if divida > 0 else max(renda * 0.08, 150)
        opcoes = []
        for n in range(2, 13):
            parcela = preco / n
            impacto = maior_fatura_futura + parcela
            if parcela <= limite_parcela_segura and (saldo_proj - parcela) > 0:
                opcoes.append((n, parcela, impacto))

        linhas.append("")
        linhas.append("Simulação de parcelamento:")
        if divida > 0 and prioridade != "alta":
            linhas.append("Mesmo parcelando, eu NÃO recomendo agora porque existe dívida ativa e o item não é essencial.")
        elif not opcoes:
            linhas.append("Nenhuma parcela ficou segura dentro da sua renda atual.")
            linhas.append("Recomendação: aguardar, quitar dívida e reavaliar no próximo mês.")
        else:
            escolhido = opcoes[0]
            if preco > renda * 0.5:
                escolhido = next((o for o in opcoes if o[0] >= 8), opcoes[-1])

            n, parcela, impacto = escolhido
            linhas.append(f"Plano recomendado: {n}x de aproximadamente R$ {parcela:.2f}")
            linhas.append(f"Fatura futura estimada com esse item: R$ {impacto:.2f}")
            linhas.append("Condição: só comprar se não houver conta atrasada e se não estourar o limite ideal do cartão.")

        linhas.append("")
        linhas.append("Ranking de prioridade:")
        linhas.append("- Geladeira/fogão/remédio/vestuário básico > celular/lazer/status")
        linhas.append("- Exemplo: geladeira é mais importante que celular; calcinha/cueca são mais importantes que luxo.")

        linhas.append("")
        if prioridade == "alta":
            linhas.append("Próximo passo: se for realmente necessário, planeje a menor parcela segura.")
        else:
            linhas.append("Próximo passo: adicione à lista de desejos e só compre depois da dívida cair.")

        return "\n".join(linhas)
