import re
import requests
import math
from datetime import datetime
from statistics import median
from urllib.parse import quote

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

def _resumo_precos(precos, fonte, exemplo, observacao=None):
    precos_ordenados = sorted(precos)
    med = float(median(precos_ordenados))
    if len(precos_ordenados) >= 5 and med > 0:
        filtrados = [p for p in precos_ordenados if med * 0.45 <= p <= med * 1.8]
        if len(filtrados) >= 3:
            precos_ordenados = filtrados
    precos_base = precos_ordenados
    if len(precos_ordenados) >= 8:
        corte = max(1, int(len(precos_ordenados) * 0.1))
        precos_base = precos_ordenados[corte:-corte] or precos_ordenados
    return {
        "ok": True,
        "preco_mediano": round(float(median(precos_ordenados)), 2),
        "preco_medio": round(sum(precos_base) / len(precos_base), 2),
        "preco_minimo": round(min(precos_ordenados), 2),
        "preco_maximo": round(max(precos_ordenados), 2),
        "qtd": len(precos_ordenados),
        "fonte": fonte,
        "exemplo": exemplo,
        "observacao": observacao,
    }


def buscar_preco_kabum(produto, observacao=None):
    try:
        url = "https://www.kabum.com.br/busca/" + quote(produto)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
        try:
            r = requests.get(url, headers=headers, timeout=12)
        except requests.exceptions.SSLError:
            requests.packages.urllib3.disable_warnings()
            r = requests.get(url, headers=headers, timeout=12, verify=False)
        if not r.ok:
            return {"ok": False, "erro": f"KaBuM HTTP {r.status_code}"}

        raw_prices = re.findall(r'"priceWithDiscount"\s*:\s*([0-9]+(?:\.[0-9]+)?)', r.text)
        if not raw_prices:
            raw_prices = re.findall(r'"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)', r.text)
        precos = []
        for raw in raw_prices[:30]:
            try:
                valor = float(raw)
            except ValueError:
                continue
            if valor >= 20:
                precos.append(valor)

        if not precos:
            return {"ok": False, "erro": "sem precos encontrados na KaBuM"}

        return _resumo_precos(precos[:20], "KaBuM", produto, observacao)
    except Exception as e:
        return {"ok": False, "erro": str(e)}


def buscar_preco_mercado_livre(produto):
    try:
        url = "https://api.mercadolibre.com/sites/MLB/search"
        params = {"q": produto, "limit": 20}
        headers = {
            "User-Agent": "NEXUS-Financeiro/1.0 (+https://github.com/luizsoberanu-droid/financeiro-telegram)",
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
        try:
            r = requests.get(url, params=params, headers=headers, timeout=12)
        except requests.exceptions.SSLError:
            requests.packages.urllib3.disable_warnings()
            r = requests.get(url, params=params, headers=headers, timeout=12, verify=False)
        if not r.ok:
            fallback = buscar_preco_kabum(produto, f"Mercado Livre indisponivel: HTTP {r.status_code}")
            return fallback if fallback.get("ok") else {"ok": False, "erro": f"Mercado Livre HTTP {r.status_code}; {fallback.get('erro')}"}
        data = r.json()
        results = data.get("results", [])[:20]
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
        return _resumo_precos(precos, "Mercado Livre", titulos[0] if titulos else produto)
    except Exception as e:
        fallback = buscar_preco_kabum(produto, f"Mercado Livre indisponivel: {e}")
        return fallback if fallback.get("ok") else {"ok": False, "erro": str(e)}

class WishlistAdvisorService:
    def __init__(self, db_session):
        self.db = db_session

    def registrar_preco_desejo(self, desejo, preco_info, mes_ref=None):
        if not desejo or not preco_info or not preco_info.get("ok"):
            return None

        from models.database import PrecoDesejoHistorico

        mes_ref = mes_ref or datetime.now().strftime("%Y-%m")
        desejo.preco_fonte = preco_info.get("fonte")
        desejo.preco_medio = float(preco_info.get("preco_medio") or 0)
        desejo.preco_mediano = float(preco_info.get("preco_mediano") or 0)
        desejo.preco_minimo = float(preco_info.get("preco_minimo") or 0)
        desejo.preco_maximo = float(preco_info.get("preco_maximo") or 0)
        desejo.preco_qtd = int(preco_info.get("qtd") or 0)
        desejo.preco_exemplo = preco_info.get("exemplo")
        desejo.preco_atualizado_em = datetime.utcnow()

        historico = self.db.query(PrecoDesejoHistorico).filter(
            PrecoDesejoHistorico.desejo_id == desejo.id,
            PrecoDesejoHistorico.mes_ref == mes_ref
        ).first()
        if not historico:
            historico = PrecoDesejoHistorico(desejo_id=desejo.id, nome=desejo.nome, mes_ref=mes_ref)
            self.db.add(historico)

        historico.nome = desejo.nome
        historico.preco_medio = desejo.preco_medio
        historico.preco_mediano = desejo.preco_mediano
        historico.preco_minimo = desejo.preco_minimo
        historico.preco_maximo = desejo.preco_maximo
        historico.qtd_anuncios = desejo.preco_qtd
        historico.fonte = desejo.preco_fonte
        historico.exemplo = desejo.preco_exemplo

        return historico

    def atualizar_preco_desejo(self, desejo, mes_ref=None):
        preco_anterior = float(desejo.valor or 0)
        preco_info = buscar_preco_mercado_livre(desejo.nome)
        if not preco_info.get("ok"):
            return {
                "ok": False,
                "desejo": desejo.nome,
                "erro": preco_info.get("erro", "nao foi possivel buscar preco real"),
            }

        preco_atual = float(preco_info.get("preco_medio") or preco_info.get("preco_mediano") or 0)
        desejo.valor = round(preco_atual, 2)
        self.registrar_preco_desejo(desejo, preco_info, mes_ref)
        self.db.commit()

        queda_pct = 0
        if preco_anterior > 0 and preco_atual < preco_anterior:
            queda_pct = ((preco_anterior - preco_atual) / preco_anterior) * 100

        return {
            "ok": True,
            "desejo": desejo.nome,
            "preco_anterior": round(preco_anterior, 2),
            "preco_atual": round(preco_atual, 2),
            "queda_pct": round(queda_pct, 1),
            "preco_info": preco_info,
        }

    def revisar_precos_mensal(self):
        from models.database import Desejo

        desejos = self.db.query(Desejo).filter(Desejo.comprado == False).order_by(Desejo.created_at.desc()).all()
        mes_ref = datetime.now().strftime("%Y-%m")
        resultados = []
        destaques = []

        for desejo in desejos:
            atualizacao = self.atualizar_preco_desejo(desejo, mes_ref)
            resultados.append(atualizacao)
            if not atualizacao.get("ok"):
                continue

            diag = self.diagnostico_compra(desejo.nome, atualizacao["preco_atual"])
            atualizacao["diagnostico"] = diag

            queda = atualizacao.get("queda_pct", 0)
            liberado = diag.get("decisao") in ["PODE_PLANEJAR", "PARCELADO_COM_CONTROLE"]
            if queda >= 5 or liberado:
                destaques.append((atualizacao, diag))

        linhas = ["Revisao mensal da lista de desejos", ""]
        if not desejos:
            linhas.append("Sua lista ainda esta vazia. Me diga um item e eu busco a media real na internet antes de salvar.")
        elif not destaques:
            linhas.append("Revisei os precos reais dos desejos cadastrados. Ainda nao apareceu queda forte nem compra claramente segura.")
            linhas.append("Vou continuar acompanhando a media mensal.")
        else:
            linhas.append("Encontrei pontos para avaliar:")
            for atualizacao, diag in destaques[:6]:
                linhas.append(
                    f"- {atualizacao['desejo']}: media R$ {atualizacao['preco_atual']:.2f} "
                    f"({atualizacao['queda_pct']:.1f}% abaixo da referencia anterior). "
                    f"Decisao: {diag.get('decisao')}. Melhor caminho: {diag.get('melhor_caminho')}"
                )

        linhas.append("")
        linhas.append("Regra: queda de preco so vira compra se saldo, dividas, fatura e reserva continuarem saudaveis.")
        return {
            "ok": True,
            "mes_ref": mes_ref,
            "total_desejos": len(desejos),
            "resultados": resultados,
            "mensagem": "\n".join(linhas),
        }

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

    def diagnostico_compra(self, produto, preco_informado=None):
        produto = limpar_query(produto)
        prioridade = classificar_prioridade(produto)
        motivo = explicar_prioridade(produto, prioridade)

        preco_info = None
        preco = preco_informado
        if preco is None:
            preco_info = buscar_preco_mercado_livre(produto)
            if preco_info.get("ok"):
                preco = preco_info["preco_medio"]

        preco = float(preco or 0)
        saldo, dividas = self._dados_financeiros()
        saldo_proj = saldo.get("saldo_projetado", 0)
        divida = dividas.get("total_divida", 0)
        renda = saldo.get("receita_total", 0)

        faturas = self._faturas_futuras_cartao(6)
        maior_fatura_futura = max(faturas.values()) if faturas else 0

        from services.card_limit_service import CardLimitService
        limites_cartao = CardLimitService(self.db).resumo_limites()
        disponivel_seguro_mes = limites_cartao.get("disponivel_seguro_mes", 0)
        cartoes = limites_cartao.get("cartoes", [])
        maior_disponivel_real = max([c.get("disponivel_real", 0) for c in cartoes], default=0)
        tem_limite_real = limites_cartao.get("limite_total_real", 0) > 0

        limite_parcela_segura = max(renda * 0.05, 100) if divida > 0 else max(renda * 0.08, 150)
        opcoes = []
        if preco > 0:
            for n in range(2, 13):
                parcela = preco / n
                if tem_limite_real and preco > maior_disponivel_real:
                    continue
                if parcela <= limite_parcela_segura and parcela <= max(disponivel_seguro_mes, limite_parcela_segura) and (saldo_proj - parcela) > 0:
                    opcoes.append({
                        "parcelas": n,
                        "valor_parcela": round(parcela, 2),
                        "fatura_estimada": round(maior_fatura_futura + parcela, 2),
                    })

        saldo_apos_avista = saldo_proj - preco
        capacidade_mes = max(min(max(saldo_proj, 0) * 0.7, renda * 0.12), renda * 0.05, 50)
        meses_para_juntar = max(math.ceil(max(preco - max(saldo_proj, 0), 0) / capacidade_mes), 1) if preco > 0 else None
        meses_para_reduzir_divida = max(math.ceil(divida / max(capacidade_mes, 1)), 1) if divida > 0 else 0

        motivos = []
        if preco <= 0:
            return {
                "produto": produto,
                "preco": 0,
                "prioridade": prioridade,
                "motivo_prioridade": motivo,
                "decisao": "PRECISO_DO_VALOR",
                "melhor_caminho": "Informe o valor para eu calcular a vista, parcelado e prazo.",
                "quando_comprar": "Depois que o valor for informado.",
                "pagamento_recomendado": "indefinido",
                "parcelas_recomendadas": None,
                "valor_parcela_recomendado": None,
                "motivos": ["Sem valor nao existe simulacao confiavel."],
                "preco_fonte": preco_info.get("fonte") if preco_info else None,
            }

        if divida > 0 and prioridade != "alta":
            motivos.append("Existe divida ativa e o item nao e essencial.")
            return {
                "produto": produto,
                "preco": round(preco, 2),
                "prioridade": prioridade,
                "motivo_prioridade": motivo,
                "decisao": "NAO_COMPRAR_AGORA",
                "melhor_caminho": "Guardar na lista, quitar/reduzir dividas e reavaliar antes de usar cartao.",
                "quando_comprar": f"Reavaliar em aproximadamente {meses_para_reduzir_divida} mes(es), depois da fase de dividas aliviar.",
                "pagamento_recomendado": "esperar",
                "parcelas_recomendadas": None,
                "valor_parcela_recomendado": None,
                "motivos": motivos,
                "preco_fonte": preco_info.get("fonte") if preco_info else "valor informado",
            }

        if saldo_apos_avista >= 0 and divida <= 0 and prioridade == "alta":
            return {
                "produto": produto,
                "preco": round(preco, 2),
                "prioridade": prioridade,
                "motivo_prioridade": motivo,
                "decisao": "PODE_PLANEJAR",
                "melhor_caminho": "A vista, se nao reduzir sua reserva nem atrasar conta essencial.",
                "quando_comprar": "Pode avaliar neste mes com conferencia final da reserva.",
                "pagamento_recomendado": "a_vista",
                "parcelas_recomendadas": None,
                "valor_parcela_recomendado": None,
                "motivos": ["Item prioritario e saldo comporta a compra a vista."],
                "preco_fonte": preco_info.get("fonte") if preco_info else "valor informado",
            }

        if opcoes:
            escolhido = opcoes[0]
            if preco > renda * 0.5:
                escolhido = next((o for o in opcoes if o["parcelas"] >= 8), opcoes[-1])
            return {
                "produto": produto,
                "preco": round(preco, 2),
                "prioridade": prioridade,
                "motivo_prioridade": motivo,
                "decisao": "PARCELADO_COM_CONTROLE",
                "melhor_caminho": f"Parcelar em {escolhido['parcelas']}x de R$ {escolhido['valor_parcela']:.2f}, sem ultrapassar o limite seguro do mes.",
                "quando_comprar": "Pode planejar quando nao houver conta atrasada e a fatura continuar dentro do limite seguro.",
                "pagamento_recomendado": "parcelado",
                "parcelas_recomendadas": escolhido["parcelas"],
                "valor_parcela_recomendado": escolhido["valor_parcela"],
                "motivos": ["Parcela cabe no limite mensal seguro e nao deixa saldo projetado negativo."],
                "preco_fonte": preco_info.get("fonte") if preco_info else "valor informado",
            }

        if tem_limite_real and preco > maior_disponivel_real:
            motivos.append(f"O valor passa do maior limite real disponivel em um cartao: R$ {maior_disponivel_real:.2f}.")
        if saldo_apos_avista < 0:
            motivos.append("A vista deixaria o saldo projetado negativo.")
        if not opcoes:
            motivos.append("Nenhuma parcela ficou segura dentro da renda e do limite mensal.")

        return {
            "produto": produto,
            "preco": round(preco, 2),
            "prioridade": prioridade,
            "motivo_prioridade": motivo,
            "decisao": "AGUARDAR_PLANEJANDO",
            "melhor_caminho": f"Guardar cerca de R$ {min(capacidade_mes, preco):.2f}/mes e comprar sem pressionar a fatura.",
            "quando_comprar": f"Daqui a aproximadamente {meses_para_juntar} mes(es), reavaliando renda, dividas e limite.",
            "pagamento_recomendado": "juntar_primeiro",
            "parcelas_recomendadas": None,
            "valor_parcela_recomendado": None,
            "motivos": motivos or ["Compra exige mais folga no orcamento."],
            "preco_fonte": preco_info.get("fonte") if preco_info else "valor informado",
        }

    def analisar_compra(self, produto, preco_informado=None):
        produto = limpar_query(produto)
        prioridade = classificar_prioridade(produto)
        motivo = explicar_prioridade(produto, prioridade)

        preco_info = None
        preco = preco_informado
        if preco is None:
            preco_info = buscar_preco_mercado_livre(produto)
            if preco_info.get("ok"):
                preco = preco_info["preco_medio"]

        diagnostico = self.diagnostico_compra(produto, preco if preco is not None else None)

        saldo, dividas = self._dados_financeiros()
        saldo_proj = saldo.get("saldo_projetado", 0)
        divida = dividas.get("total_divida", 0)
        renda = saldo.get("receita_total", 0)
        contas = saldo.get("contas_pendentes", 0)
        gastos = saldo.get("gastos_mes", 0)
        parcelas_mes = saldo.get("parcelas_mes", 0)

        faturas = self._faturas_futuras_cartao(6)
        maior_fatura_futura = max(faturas.values()) if faturas else 0
        from services.card_limit_service import CardLimitService
        limites_cartao = CardLimitService(self.db).resumo_limites()
        disponivel_seguro_mes = limites_cartao.get("disponivel_seguro_mes", 0)
        maior_disponivel_real = max([c.get("disponivel_real", 0) for c in limites_cartao.get("cartoes", [])], default=0)

        linhas = []
        linhas.append("🧠 ANÁLISE DE DESEJO — DISCIPLINA PESADA")
        linhas.append("")
        linhas.append(f"Item analisado: {produto}")
        linhas.append(f"Prioridade: {prioridade.upper()} — {motivo}")
        linhas.append(f"Decisao direta: {diagnostico['decisao']}")
        linhas.append(f"Melhor caminho: {diagnostico['melhor_caminho']}")
        linhas.append(f"Quando comprar: {diagnostico['quando_comprar']}")

        if preco is not None:
            linhas.append(f"Preço usado na análise: R$ {preco:.2f}")
            if preco_info and preco_info.get("ok"):
                linhas.append(f"Fonte: {preco_info['fonte']} - media de {preco_info['qtd']} anuncios")
        else:
            linhas.append("Nao consegui buscar preco real agora. Me envie assim: quero comprar item de 2500")
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
        linhas.append(f"- Limite seguro de cartao ainda disponivel no mes: R$ {disponivel_seguro_mes:.2f}")
        if limites_cartao.get("limite_total_real", 0) > 0:
            linhas.append(f"- Maior limite real disponivel em um cartao: R$ {maior_disponivel_real:.2f}")
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
            if parcela <= limite_parcela_segura and parcela <= max(disponivel_seguro_mes, limite_parcela_segura) and (saldo_proj - parcela) > 0:
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
        linhas.append("Quando posso comprar:")
        if divida > 0 and prioridade != "alta":
            linhas.append("Depois de reduzir ou quitar as dividas ativas. Hoje esse item compete com sua recuperacao financeira.")
        elif preco > 0 and saldo_proj >= preco and prioridade == "alta":
            linhas.append("Pode avaliar ainda neste mes, desde que a compra nao reduza a reserva nem use limite acima do seguro.")
        elif preco > 0:
            base_aporte = max(disponivel_seguro_mes, saldo_proj * 0.5, renda * 0.05, 1)
            meses = max(math.ceil(max(preco - max(saldo_proj, 0), 0) / base_aporte), 1)
            linhas.append(f"Planeje para daqui a aproximadamente {meses} mes(es), guardando perto de R$ {min(base_aporte, preco):.2f}/mes e reavaliando a fatura.")

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
