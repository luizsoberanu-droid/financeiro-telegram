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
            "User-Agent": "AurumCapital/1.0 (+https://github.com/luizsoberanu-droid/financeiro-telegram)",
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

    def _moeda(self, valor):
        return f"R$ {float(valor or 0):.2f}".replace(".", ",")

    def _normalizar_urgencia(self, urgencia):
        u = (urgencia or "normal").lower().strip()
        mapa = {
            "critica": "critica",
            "crítica": "critica",
            "alta": "alta",
            "urgente": "alta",
            "media": "media",
            "média": "media",
            "normal": "normal",
            "baixa": "baixa",
        }
        return mapa.get(u, "normal")

    def _somar_meses(self, data, meses):
        meses = max(int(meses or 1), 1)
        mes = data.month - 1 + meses
        ano = data.year + mes // 12
        mes = mes % 12 + 1
        dia = min(data.day, [31, 29 if ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1])
        return data.replace(year=ano, month=mes, day=dia)

    def plano_acao_desejo(
        self,
        desejo,
        prazo_meses=None,
        urgencia=None,
        parcelas=None,
        motivo_urgencia=None,
        salvar=False,
    ):
        from services.card_limit_service import CardLimitService

        nome = getattr(desejo, "nome", str(desejo or "item"))
        valor = float(getattr(desejo, "valor", 0) or 0)
        prioridade = (getattr(desejo, "prioridade", None) or classificar_prioridade(nome) or "media").lower()
        urgencia = self._normalizar_urgencia(urgencia or getattr(desejo, "urgencia", None))
        prioridade_operacional = prioridade

        prazo_meses = int(prazo_meses or 0)
        prazo_meses = max(min(prazo_meses, 60), 0)
        prazo_calculo = max(prazo_meses, 1)
        parcelas_pedidas = int(parcelas or getattr(desejo, "parcelas_planejadas", 0) or 0)
        if parcelas_pedidas < 0:
            parcelas_pedidas = 0

        diag = self.diagnostico_compra(nome, valor)
        saldo, dividas = self._dados_financeiros()
        from services.ai_service import FinancialTools
        reserva = FinancialTools(self.db).get_reserva_status()
        renda = float(saldo.get("receita_total") or 0)
        saldo_proj = float(saldo.get("saldo_projetado", saldo.get("saldo_final", 0)) or 0)
        divida_total = float(dividas.get("total_divida") or 0)
        reserva_atual = float(reserva.get("atual") or 0)
        reserva_meta = float(reserva.get("meta") or 0)
        reserva_faltante = float(reserva.get("faltante") or 0)
        saldo_livre = max(saldo_proj, 0)
        teto_por_renda = renda * 0.12 if renda > 0 else saldo_livre
        capacidade_guardar = max(min(saldo_livre * 0.70, teto_por_renda), 0)
        if saldo_livre > 0 and capacidade_guardar <= 0:
            capacidade_guardar = min(saldo_livre, 50)

        limites = CardLimitService(self.db).resumo_limites()
        disponivel_seguro_mes = float(limites.get("disponivel_seguro_mes") or 0)
        cartoes = limites.get("cartoes", [])
        maior_disponivel_real = max([float(c.get("disponivel_real") or 0) for c in cartoes], default=0)
        tem_limite_real = float(limites.get("limite_total_real") or 0) > 0
        faturas = self._faturas_futuras_cartao(6)
        maior_fatura_futura = max(faturas.values()) if faturas else 0

        limite_parcela_segura = max(renda * 0.05, 100) if divida_total > 0 else max(renda * 0.08, 150)
        if urgencia == "critica" and prioridade_operacional == "alta" and saldo_proj > 0 and divida_total <= 0 and reserva_faltante <= 0:
            limite_parcela_segura *= 1.10

        opcoes = []
        if valor > 0:
            for n in range(2, 25):
                parcela = valor / n
                if tem_limite_real and valor > maior_disponivel_real:
                    continue
                if parcela <= limite_parcela_segura and parcela <= max(disponivel_seguro_mes, limite_parcela_segura) and (saldo_proj - parcela) > 0:
                    opcoes.append({
                        "parcelas": n,
                        "valor_parcela": round(parcela, 2),
                        "fatura_estimada": round(maior_fatura_futura + parcela, 2),
                    })

        escolhido = None
        if opcoes:
            if parcelas_pedidas:
                escolhido = next((o for o in opcoes if o["parcelas"] == parcelas_pedidas), None)
            if not escolhido and urgencia in ["alta", "critica"]:
                alvo_minimo = min(max(prazo_meses * 3, 6), 12)
                escolhido = next((o for o in opcoes if o["parcelas"] >= alvo_minimo), opcoes[-1])
            if not escolhido:
                escolhido = opcoes[0]

        data_alvo = self._somar_meses(datetime.utcnow(), prazo_meses) if prazo_meses > 0 else None
        economia_avista = valor / prazo_calculo if valor > 0 else 0
        meses_para_juntar = max(math.ceil(max(valor - saldo_livre, 0) / max(capacidade_guardar, 1)), 1) if valor > 0 else 0
        bloqueios = []
        criterios_liberacao = [
            "saldo final projetado positivo",
            "dividas quitadas ou com plano em dia",
            "reserva minima em construcao sem ser sacrificada",
            "parcela dentro do limite seguro do cartao",
        ]

        if valor <= 0:
            status = "PRECISA_DE_VALOR"
            forma = "indefinido"
            decisao = "Informe o valor ou deixe a busca de preco rodar antes de planejar a compra."
            aporte_pre_compra = 0
            colchao = 0
        elif saldo_proj <= 0:
            status = "PLANO_DE_RECUPERACAO"
            forma = "esperar"
            decisao = (
                "Nao vamos comprar agora. Voce esta sem folga de caixa; a prioridade e recompor o saldo, "
                "pagar o essencial e impedir nova parcela."
            )
            aporte_pre_compra = 0
            colchao = 0
            bloqueios.append(f"Saldo projetado sem folga: {self._moeda(saldo_proj)}.")
        elif divida_total > 0:
            status = "QUITAR_DIVIDAS_ANTES"
            forma = "esperar"
            decisao = (
                "Nao vamos comprar agora. Primeiro vem quitar ou reduzir dividas; depois montar dinheiro guardado. "
                "O item fica na lista para acompanhar preco, sem compromisso de compra."
            )
            aporte_pre_compra = 0
            colchao = 0
            bloqueios.append(f"Existe divida ativa de {self._moeda(divida_total)}.")
        elif reserva_faltante > 0:
            status = "MONTAR_RESERVA_ANTES"
            forma = "esperar"
            decisao = (
                "Ainda nao libero essa compra. Antes, precisamos ter dinheiro guardado para emergencia; "
                "sem isso, o desejo vira risco financeiro."
            )
            aporte_pre_compra = 0
            colchao = 0
            bloqueios.append(f"Reserva incompleta: falta {self._moeda(reserva_faltante)}.")
        elif prazo_meses > 0 and economia_avista <= capacidade_guardar:
            status = "COMPRAR_A_VISTA_NO_PRAZO"
            forma = "a_vista"
            decisao = f"Comprar a vista no prazo alvo, guardando {self._moeda(economia_avista)}/mes."
            aporte_pre_compra = economia_avista
            colchao = valor
        elif valor <= saldo_livre and prioridade_operacional == "alta":
            status = "COMPRA_AVISTA_LIBERADA"
            forma = "a_vista"
            decisao = "Pode comprar a vista somente se isso nao atrasar conta essencial nem reduzir sua reserva."
            aporte_pre_compra = 0
            colchao = valor
        elif escolhido and urgencia in ["alta", "critica"] and prioridade_operacional == "alta":
            status = "PARCELADO_ESSENCIAL_COM_CONTROLE"
            forma = "parcelado"
            colchao = escolhido["valor_parcela"] * 2
            aporte_pre_compra = colchao / prazo_calculo
            decisao = (
                f"So por ser item essencial, o caminho possivel e parcelar em {escolhido['parcelas']}x de "
                f"{self._moeda(escolhido['valor_parcela'])}, mantendo duas parcelas guardadas antes de executar."
            )
        elif escolhido:
            status = "PARCELADO_COM_CONTROLE"
            forma = "parcelado"
            colchao = escolhido["valor_parcela"] * 2
            aporte_pre_compra = colchao / prazo_calculo
            decisao = (
                f"Compra parcelada possivel com controle: {escolhido['parcelas']}x de "
                f"{self._moeda(escolhido['valor_parcela'])}."
            )
        else:
            status = "JUNTAR_ANTES_DE_COMPRAR"
            forma = "esperar"
            aporte_pre_compra = min(capacidade_guardar, valor)
            colchao = 0
            decisao = (
                f"Ainda nao libero compra. Melhor juntar por aproximadamente {meses_para_juntar} mes(es), "
                "reavaliar preco e so executar com saldo positivo."
            )

        if tem_limite_real and valor > maior_disponivel_real:
            bloqueios.append(f"O valor passa do maior limite real disponivel: {self._moeda(maior_disponivel_real)}.")
        if valor > 0 and not tem_limite_real and forma == "parcelado":
            bloqueios.append("Cadastre o limite real do cartao antes de executar a compra.")
        if forma == "parcelado" and escolhido and escolhido["valor_parcela"] > limite_parcela_segura:
            bloqueios.append("A parcela passa do limite seguro calculado.")
        if saldo_proj <= 0:
            bloqueios.append("Recompor saldo antes de comprar.")

        acoes = []
        if status == "PLANO_DE_RECUPERACAO":
            reduzir = abs(min(saldo_proj, 0))
            acoes = [
                "Hoje: congelar compras de desejo e usar dinheiro apenas para comida, transporte, contas e saude.",
                f"Primeiro alvo: recuperar pelo menos {self._moeda(reduzir)} para voltar ao saldo positivo.",
                "Depois: revisar dividas e reserva antes de voltar a falar em compra.",
                "Item fica salvo apenas para monitorar preco e prioridade.",
            ]
        elif status == "QUITAR_DIVIDAS_ANTES":
            meta_divida = float(dividas.get("meta_3_meses") or 0)
            aporte_divida = min(max(capacidade_guardar, 0), meta_divida or divida_total)
            acoes = [
                f"Mes atual: direcionar {self._moeda(aporte_divida)} para dividas antes de qualquer desejo.",
                "Negociar juros, quitar a menor/mais cara primeiro e nao abrir nova parcela.",
                "Quando a divida estiver zerada ou controlada, revisar este item com o saldo real do mes.",
                "Enquanto isso, manter o item na lista e acompanhar queda de preco.",
            ]
        elif status == "MONTAR_RESERVA_ANTES":
            sugestao_reserva = float(reserva.get("sugestao_mensal") or 0)
            aporte_reserva = min(max(capacidade_guardar, 0), sugestao_reserva or reserva_faltante)
            acoes = [
                f"Mes atual: guardar {self._moeda(aporte_reserva)} para reserva antes de desejo.",
                f"Meta de reserva: sair de {self._moeda(reserva_atual)} para {self._moeda(reserva_meta)}.",
                "Comprar somente necessidade real; conforto, lazer e status ficam pausados.",
                "Reavaliar o item no fechamento mensal, com reserva evoluindo.",
            ]
        elif forma == "a_vista" and prazo_meses > 0:
            acoes = [
                f"Mes 1: separar {self._moeda(aporte_pre_compra)} em um cofre do item e travar gastos extras.",
                f"Mes {prazo_meses}: comprar somente se o preco continuar ate {self._moeda(valor)} e o saldo seguir positivo.",
                "Depois da compra: recompor a reserva antes de liberar outro desejo grande.",
            ]
        elif forma == "a_vista":
            acoes = [
                "Conferir contas do mes, fatura e reserva antes de pagar.",
                "Comprar a vista apenas se o saldo final continuar positivo depois da compra.",
                "Depois da compra: pausar novos desejos grandes ate o proximo fechamento.",
            ]
        elif forma == "parcelado" and escolhido:
            etapa_compra = (
                f"Mes {prazo_meses}: revisar preco e limite; comprar em ate {escolhido['parcelas']}x de {self._moeda(escolhido['valor_parcela'])}."
                if prazo_meses > 0 else
                f"Quando os criterios forem cumpridos: comprar em ate {escolhido['parcelas']}x de {self._moeda(escolhido['valor_parcela'])}."
            )
            acoes = [
                f"Mes 1: separar {self._moeda(aporte_pre_compra)} para criar colchao de duas parcelas.",
                etapa_compra,
                "Depois da compra: bloquear novos parcelamentos ate a fatura estabilizar.",
            ]
        else:
            acoes = [
                f"Guardar o maximo seguro, hoje estimado em {self._moeda(aporte_pre_compra)}.",
                "Reavaliar saldo, dividas, reserva, limite do cartao e preco no fechamento mensal.",
                "Se continuar inseguro, manter na lista e buscar alternativa mais barata.",
            ]

        if bloqueios:
            acoes.append("Trava de seguranca: " + " ".join(bloqueios[:3]))

        parcelamento = escolhido if forma == "parcelado" else None

        linhas = [
            "Aurum Capital - plano de acao da lista de desejos",
            "",
            f"Item: {nome}",
            f"Valor: {self._moeda(valor)}",
            f"Urgencia: {urgencia.upper()}",
            (
                f"Prazo alvo informado: {prazo_meses} mes(es) ({data_alvo.strftime('%d/%m/%Y')})"
                if data_alvo else
                "Prazo alvo: sem prazo fixo; liberar somente quando a base financeira estiver saudavel"
            ),
            f"Decisao: {status}",
            f"Forma recomendada: {forma}",
            decisao,
            "",
            "Numeros do plano:",
            f"- Guardar antes da compra: {self._moeda(aporte_pre_compra)}/mes",
            f"- Limite seguro de parcela: {self._moeda(limite_parcela_segura)}",
            f"- Saldo projetado atual: {self._moeda(saldo_proj)}",
            f"- Divida ativa: {self._moeda(divida_total)}",
            f"- Reserva: {self._moeda(reserva_atual)} de {self._moeda(reserva_meta)}",
            f"- Limite real disponivel no melhor cartao: {self._moeda(maior_disponivel_real)}",
        ]
        if parcelamento:
            linhas += [
                f"- Parcelamento recomendado: {parcelamento['parcelas']}x de {self._moeda(parcelamento['valor_parcela'])}",
                f"- Fatura estimada com o item: {self._moeda(parcelamento['fatura_estimada'])}",
            ]
        linhas += ["", "Plano de acao:", *[f"- {a}" for a in acoes]]
        if motivo_urgencia:
            linhas += ["", f"Motivo da urgencia registrado: {motivo_urgencia}"]
        linhas += [
            "",
            "Criterios para liberar compra:",
            *[f"- {c}" for c in criterios_liberacao],
            "",
            "Regra: urgencia nao e autorizacao de compra. Primeiro saldo positivo, dividas sob controle e dinheiro guardado.",
        ]

        result = {
            "ok": True,
            "id": getattr(desejo, "id", None),
            "nome": nome,
            "valor": round(valor, 2),
            "prioridade": prioridade,
            "urgencia": urgencia,
            "motivo_urgencia": motivo_urgencia or getattr(desejo, "motivo_urgencia", None),
            "prazo_compra_meses": prazo_meses,
            "data_alvo_compra": data_alvo.isoformat() if data_alvo else "",
            "status_plano": status,
            "decisao": decisao,
            "forma_recomendada": forma,
            "parcelas_recomendadas": parcelamento["parcelas"] if parcelamento else None,
            "valor_parcela_recomendado": parcelamento["valor_parcela"] if parcelamento else None,
            "aporte_pre_compra_mensal": round(aporte_pre_compra, 2),
            "colchao_minimo_ate_compra": round(colchao, 2),
            "limite_parcela_segura": round(limite_parcela_segura, 2),
            "saldo_projetado": round(saldo_proj, 2),
            "maior_limite_real_cartao": round(maior_disponivel_real, 2),
            "bloqueios": bloqueios,
            "acoes": acoes,
            "criterios_liberacao": criterios_liberacao,
            "fundacao_financeira": {
                "saldo_ok": saldo_proj > 0,
                "dividas_ok": divida_total <= 0,
                "reserva_ok": reserva_faltante <= 0,
                "saldo_projetado": round(saldo_proj, 2),
                "divida_total": round(divida_total, 2),
                "reserva_faltante": round(reserva_faltante, 2),
            },
            "diagnostico": diag,
            "mensagem": "\n".join(linhas),
        }

        if salvar and hasattr(desejo, "nome"):
            desejo.urgencia = urgencia
            desejo.motivo_urgencia = motivo_urgencia or desejo.motivo_urgencia
            desejo.prazo_compra_meses = prazo_meses
            desejo.data_alvo_compra = data_alvo
            desejo.forma_pagamento_planejada = forma
            desejo.parcelas_planejadas = parcelamento["parcelas"] if parcelamento else 0
            desejo.valor_parcela_planejada = parcelamento["valor_parcela"] if parcelamento else 0
            desejo.plano_acao = result["mensagem"]
            desejo.updated_at = datetime.utcnow()
            self.db.commit()

        return result

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

    def ranking_inteligente(self, limite=10):
        from models.database import Desejo

        urgencia_rank = {"critica": 0, "alta": 1, "media": 2, "normal": 3, "baixa": 4}
        prioridade_rank = {"alta": 1, "media": 2, "baixa": 3}
        decisao_rank = {
            "PODE_PLANEJAR": 1,
            "PARCELADO_COM_CONTROLE": 2,
            "AGUARDAR_PLANEJANDO": 3,
            "NAO_COMPRAR_AGORA": 4,
            "PRECISO_DO_VALOR": 5,
        }

        desejos = self.db.query(Desejo).filter(Desejo.comprado == False).all()
        rows = []
        for desejo in desejos:
            diag = self.diagnostico_compra(desejo.nome, desejo.valor or 0)
            prioridade = (desejo.prioridade or diag.get("prioridade") or "media").lower()
            urgencia = self._normalizar_urgencia(getattr(desejo, "urgencia", "normal"))
            decisao = diag.get("decisao") or "AGUARDAR_PLANEJANDO"
            score = (
                urgencia_rank.get(urgencia, 3) * 1000
                + prioridade_rank.get(prioridade, 2) * 100
                + decisao_rank.get(decisao, 4) * 10
                + min(float(desejo.valor or 0) / 1000, 9)
            )
            rows.append({
                "id": desejo.id,
                "nome": desejo.nome,
                "valor": round(desejo.valor or 0, 2),
                "prioridade": prioridade,
                "urgencia": urgencia,
                "prazo_compra_meses": int(getattr(desejo, "prazo_compra_meses", 0) or 0),
                "score": round(score, 2),
                "decisao": decisao,
                "melhor_caminho": diag.get("melhor_caminho"),
                "quando_comprar": diag.get("quando_comprar"),
                "pagamento_recomendado": diag.get("pagamento_recomendado"),
                "parcelas_recomendadas": diag.get("parcelas_recomendadas"),
                "valor_parcela_recomendado": diag.get("valor_parcela_recomendado"),
                "motivos": diag.get("motivos", []),
            })

        rows.sort(key=lambda item: item["score"])
        return rows[:limite]

    def radar_oportunidades(self, limite=10):
        from models.database import Desejo, PrecoDesejoHistorico

        desejos = self.db.query(Desejo).filter(Desejo.comprado == False).all()
        oportunidades = []

        for desejo in desejos:
            atual = float(desejo.valor or desejo.preco_medio or 0)
            historicos = (
                self.db.query(PrecoDesejoHistorico)
                .filter(PrecoDesejoHistorico.desejo_id == desejo.id)
                .order_by(PrecoDesejoHistorico.mes_ref.desc())
                .all()
            )
            referencias = [
                float(h.preco_medio or h.preco_mediano or 0)
                for h in historicos
                if float(h.preco_medio or h.preco_mediano or 0) > 0
            ]
            referencia = referencias[1] if len(referencias) > 1 else (referencias[0] if referencias else atual)
            queda_pct = 0
            if referencia and atual and atual < referencia:
                queda_pct = ((referencia - atual) / referencia) * 100

            diag = self.diagnostico_compra(desejo.nome, atual)
            destaque = queda_pct >= 5 or diag.get("decisao") in ["PODE_PLANEJAR", "PARCELADO_COM_CONTROLE"]
            oportunidades.append({
                "id": desejo.id,
                "nome": desejo.nome,
                "valor_atual": round(atual, 2),
                "referencia": round(referencia or 0, 2),
                "queda_pct": round(queda_pct, 1),
                "destaque": bool(destaque),
                "decisao": diag.get("decisao"),
                "melhor_caminho": diag.get("melhor_caminho"),
                "quando_comprar": diag.get("quando_comprar"),
                "preco_fonte": desejo.preco_fonte,
            })

        oportunidades.sort(key=lambda item: (not item["destaque"], -item["queda_pct"], item["valor_atual"]))

        linhas = ["Radar de oportunidades da lista de desejos", ""]
        destaques = [o for o in oportunidades if o["destaque"]]
        if not oportunidades:
            linhas.append("Sua lista de desejos esta vazia. Me diga um item e eu busco a media real antes de salvar.")
        elif not destaques:
            linhas.append("Nao encontrei queda relevante nem compra claramente segura agora.")
            linhas.append("A melhor atitude e manter a lista ordenada e revisar no proximo fechamento.")
        else:
            linhas.append("Itens que merecem sua atencao:")
            for item in destaques[:limite]:
                linhas.append(
                    f"- {item['nome']}: R$ {item['valor_atual']:.2f} | queda {item['queda_pct']:.1f}% | "
                    f"{item['decisao']} | {item['melhor_caminho']}"
                )
        linhas.append("")
        linhas.append("Regra: queda de preco nao libera compra sozinha; ela precisa caber no saldo, reserva, dividas e cartao.")

        return {
            "ok": True,
            "oportunidades": oportunidades[:limite],
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
        from services.ai_service import FinancialTools
        reserva = FinancialTools(self.db).get_reserva_status()
        saldo_proj = saldo.get("saldo_projetado", 0)
        divida = dividas.get("total_divida", 0)
        renda = saldo.get("receita_total", 0)
        reserva_faltante = reserva.get("faltante", 0)

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

        if saldo_proj <= 0:
            motivos.append("Saldo projetado sem folga. Comprar agora aumenta risco de fechar o mes no negativo.")
            return {
                "produto": produto,
                "preco": round(preco, 2),
                "prioridade": prioridade,
                "motivo_prioridade": motivo,
                "decisao": "NAO_COMPRAR_AGORA",
                "melhor_caminho": "Pausar a compra, recompor saldo e montar um plano de acao antes de assumir qualquer parcela.",
                "quando_comprar": "Depois que o saldo final projetado voltar ao positivo e as contas essenciais estiverem cobertas.",
                "pagamento_recomendado": "esperar",
                "parcelas_recomendadas": None,
                "valor_parcela_recomendado": None,
                "motivos": motivos,
                "preco_fonte": preco_info.get("fonte") if preco_info else "valor informado",
            }

        if divida > 0:
            motivos.append("Existe divida ativa. A prioridade e reduzir divida antes de comprar desejo.")
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

        if reserva_faltante > 0:
            motivos.append("Reserva de emergencia ainda incompleta. Sem dinheiro guardado, desejo vira risco.")
            return {
                "produto": produto,
                "preco": round(preco, 2),
                "prioridade": prioridade,
                "motivo_prioridade": motivo,
                "decisao": "NAO_COMPRAR_AGORA",
                "melhor_caminho": "Manter o item na lista e direcionar a sobra para reserva antes de comprar.",
                "quando_comprar": "Depois de evoluir a reserva e confirmar que a compra nao prejudica o caixa.",
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
