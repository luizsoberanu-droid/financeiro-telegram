import os
from datetime import datetime


class AdvisorService:
    def __init__(self, db_session):
        self.db = db_session

    def _moeda(self, valor):
        valor = float(valor or 0)
        sinal = "-R$ " if valor < 0 else "R$ "
        texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return sinal + texto

    def chat_ids_destino(self):
        chat_env = os.getenv("TELEGRAM_DEFAULT_CHAT_ID", "").strip()
        if chat_env:
            return [chat_env]
        try:
            from models.database import Conversa
            ids = [
                row[0]
                for row in self.db.query(Conversa.chat_id).distinct().all()
                if row[0] and row[0] != "default"
            ]
            return ids or ["default"]
        except Exception:
            return ["default"]

    def saldo_utilizacao(self):
        from services.ai_service import FinancialTools
        from services.card_limit_service import CardLimitService

        tools = FinancialTools(self.db)
        saldo = tools.get_saldo_atual()
        dividas = tools.get_analise_dividas()
        reserva = tools.get_reserva_status()
        limites = CardLimitService(self.db).resumo_limites()

        receita_total = float(saldo.get("receita_total") or 0)
        saldo_final = float(saldo.get("saldo_final", saldo.get("saldo_projetado", 0)) or 0)
        saldo_inicial = float(saldo.get("saldo_inicial") or 0)
        movimento_mes = float(saldo.get("movimento_mes") or 0)
        gastos_mes = float(saldo.get("gastos_mes") or 0)
        parcelas_mes = float(saldo.get("parcelas_mes") or 0)
        usado_no_mes = max(gastos_mes + parcelas_mes, 0)
        divida_total = float(dividas.get("total_divida") or saldo.get("divida_total") or 0)
        reserva_faltante = float(reserva.get("faltante") or 0)
        credito_seguro = float(limites.get("disponivel_seguro_mes") or 0)

        saldo_calibrado = bool(saldo.get("saldo_conta_mes_ref") == saldo.get("mes_ref"))
        base_calculo = receita_total if receita_total > 0 else max(saldo_final, 0)

        if saldo_final < 0:
            percentual_seguro = 0
            limite_mensal_seguro = 0
        elif divida_total > 0:
            percentual_seguro = 0.05
            limite_mensal_seguro = min(base_calculo * percentual_seguro, saldo_final * 0.10)
        elif reserva_faltante > 0:
            percentual_seguro = 0.10
            limite_mensal_seguro = min(base_calculo * percentual_seguro, saldo_final * 0.20)
        else:
            percentual_seguro = 0.15
            limite_mensal_seguro = min(base_calculo * percentual_seguro, saldo_final * 0.30)

        limite_mensal_seguro = round(max(limite_mensal_seguro, 0), 2)
        margem_restante = round(max(limite_mensal_seguro - usado_no_mes, 0), 2)
        excesso_mes = round(max(usado_no_mes - limite_mensal_seguro, 0), 2)

        if saldo_final < 0:
            status = "usar_menos"
            direcao = "usar_menos"
            reduzir_agora = round(max(abs(saldo_final), excesso_mes), 2)
            pode_usar_ate = 0
            decisao_curta = "USAR MENOS AGORA"
            mensagem_curta = f"Use menos: reduza {self._moeda(reduzir_agora)} para voltar ao azul."
            orientacao = "Congele compras nao essenciais ate o saldo final projetado ficar positivo."
        elif excesso_mes > 0:
            status = "usar_menos"
            direcao = "usar_menos"
            reduzir_agora = excesso_mes
            pode_usar_ate = 0
            decisao_curta = "USAR MENOS ESTE MES"
            mensagem_curta = f"Voce passou {self._moeda(reduzir_agora)} da margem segura."
            orientacao = "Segure novas compras e use qualquer sobra para recompor caixa, dividas ou reserva."
        elif margem_restante <= 0:
            status = "segurar"
            direcao = "usar_menos"
            reduzir_agora = 0
            pode_usar_ate = 0
            decisao_curta = "SEGURAR GASTOS"
            mensagem_curta = "Nao ha saldo livre seguro para compras extras neste mes."
            orientacao = "Use dinheiro apenas para necessidade real ate o fechamento do mes."
        else:
            status = "pode_usar"
            direcao = "pode_usar_mais_com_limite"
            reduzir_agora = 0
            pode_usar_ate = margem_restante
            decisao_curta = "PODE USAR COM LIMITE"
            mensagem_curta = f"Pode usar ate {self._moeda(pode_usar_ate)} no restante do mes."
            orientacao = "Esse valor e a margem livre segura; acima disso eu recomendo travar e revisar antes de comprar."

        if not saldo_calibrado:
            orientacao += " Atualize o saldo real de hoje para eu ficar mais preciso."

        linhas = [
            "Aurum Capital - uso seguro do saldo",
            "",
            f"Decisao: {decisao_curta}",
            f"Saldo final projetado: {self._moeda(saldo_final)}",
            f"Uso livre seguro restante: {self._moeda(pode_usar_ate)}",
            f"Quanto reduzir agora: {self._moeda(reduzir_agora)}",
            f"Limite mensal seguro: {self._moeda(limite_mensal_seguro)}",
            f"Ja usado no mes: {self._moeda(usado_no_mes)}",
            f"Credito seguro disponivel: {self._moeda(credito_seguro)}",
            "",
            mensagem_curta,
            orientacao,
        ]

        return {
            "ok": True,
            "status": status,
            "direcao": direcao,
            "decisao_curta": decisao_curta,
            "pode_usar_ate": round(pode_usar_ate, 2),
            "reduzir_agora": round(reduzir_agora, 2),
            "limite_mensal_seguro": limite_mensal_seguro,
            "usado_no_mes": round(usado_no_mes, 2),
            "percentual_seguro": percentual_seguro,
            "saldo_final": round(saldo_final, 2),
            "saldo_inicial": round(saldo_inicial, 2),
            "movimento_mes": round(movimento_mes, 2),
            "receita_total": round(receita_total, 2),
            "divida_total": round(divida_total, 2),
            "reserva_faltante": round(reserva_faltante, 2),
            "limite_credito_seguro": round(credito_seguro, 2),
            "saldo_calibrado": saldo_calibrado,
            "mes_ref": saldo.get("mes_ref"),
            "mensagem_curta": mensagem_curta,
            "orientacao": orientacao,
            "mensagem": "\n".join(linhas),
        }

    def checkup_patrimonial(self, limite_desejos=6):
        from models.database import Desejo
        from services.ai_service import FinancialTools
        from services.card_limit_service import CardLimitService
        from services.wishlist_advisor_service import WishlistAdvisorService, chave_prioridade_desejo

        tools = FinancialTools(self.db)
        saldo = tools.get_saldo_atual()
        dividas = tools.get_analise_dividas()
        reserva = tools.get_reserva_status()
        visao = tools.get_visao_patrimonial()
        limites = CardLimitService(self.db).resumo_limites()
        wishlist = WishlistAdvisorService(self.db)
        uso_saldo = self.saldo_utilizacao()

        saldo_final = saldo.get("saldo_final", saldo.get("saldo_projetado", 0)) or 0
        divida_total = dividas.get("total_divida", 0) or 0
        reserva_faltante = reserva.get("faltante", 0) or 0
        disponivel_seguro = uso_saldo.get("limite_credito_seguro", limites.get("disponivel_seguro_mes", 0)) or 0

        if saldo_final < 0:
            decisao = "NAO comprar desejos agora. Primeiro recompor saldo."
            risco = "critico"
        elif divida_total > 0:
            decisao = "NAO comprar itens nao essenciais. Prioridade e reduzir dividas."
            risco = "alto"
        elif reserva_faltante > 0:
            decisao = "Comprar somente necessidade real. O foco e completar a reserva."
            risco = "moderado"
        else:
            decisao = "Pode planejar compras com controle, sem passar do limite seguro."
            risco = "controlado"

        prioridade_rank = {"alta": 1, "media": 2, "média": 2, "baixa": 3}
        desejos = [
            d for d in self.db.query(Desejo).filter(Desejo.comprado == False).all()
        ]
        desejos.sort(key=lambda d: chave_prioridade_desejo(d.nome, d.prioridade, d.urgencia, d.valor, d.created_at))

        desejos_linhas = []
        necessidades_casa = []
        for d in desejos[:limite_desejos]:
            diag = wishlist.diagnostico_compra(d.nome, d.valor or 0)
            prioridade = (d.prioridade or "media").lower()
            if prioridade == "alta":
                necessidades_casa.append(d.nome)
            desejos_linhas.append(
                f"- {d.nome}: R$ {(d.valor or 0):.2f} | prioridade {prioridade.upper()} | "
                f"{diag.get('decisao')} | {diag.get('melhor_caminho')}"
            )

        if not desejos_linhas:
            desejos_linhas.append("- Nenhum desejo cadastrado. Me diga algo como: adicionar geladeira na lista de desejos.")

        cartoes_linhas = []
        for c in limites.get("cartoes", []):
            cartoes_linhas.append(
                f"- {c['nome']}: disponivel real R$ {c['disponivel_real']:.2f} | "
                f"seguro no mes R$ {c['disponivel_seguro_mes']:.2f} | usado R$ {c['uso_mes']:.2f}"
            )
        if not cartoes_linhas:
            cartoes_linhas.append("- Nenhum cartao cadastrado com limite real. Informe o limite para eu controlar seu credito.")

        proximas_acoes = []
        if uso_saldo.get("reduzir_agora", 0) > 0:
            proximas_acoes.append(f"Reduzir {self._moeda(uso_saldo.get('reduzir_agora'))} em compras extras para voltar ao plano.")
        elif uso_saldo.get("pode_usar_ate", 0) > 0:
            proximas_acoes.append(f"Manter compras livres ate {self._moeda(uso_saldo.get('pode_usar_ate'))} no restante do mes.")
        else:
            proximas_acoes.append("Travar compras extras e usar dinheiro apenas para necessidade real.")
        if divida_total > 0:
            proximas_acoes.append(f"Separar R$ {dividas.get('meta_3_meses', 0):.2f}/mes para atacar dividas.")
        if reserva_faltante > 0:
            proximas_acoes.append(f"Guardar R$ {reserva.get('sugestao_mensal', 0):.2f}/mes para reserva.")
        if disponivel_seguro <= 0 and limites.get("limite_total_seguro_mes", 0) > 0:
            proximas_acoes.append("Congelar cartao ate virar o mes ou baixar a fatura.")
        if necessidades_casa:
            proximas_acoes.append("Priorizar necessidades de casa: " + ", ".join(necessidades_casa[:3]) + ".")
        if not proximas_acoes:
            proximas_acoes.append("Manter gasto livre dentro do limite seguro e revisar desejos antes de comprar.")

        linhas = [
            "Aurum Capital - check-up do analista patrimonial",
            "",
            f"Risco do mes: {risco.upper()}",
            f"Decisao: {decisao}",
            f"Fase: {visao.get('fase')} | Foco: {visao.get('foco')}",
            "",
            "Resumo financeiro:",
            f"- Saldo final projetado: R$ {saldo_final:.2f}",
            f"- Uso do saldo: {uso_saldo.get('mensagem_curta')}",
            f"- Margem livre segura: {self._moeda(uso_saldo.get('pode_usar_ate'))}",
            f"- Reducao necessaria: {self._moeda(uso_saldo.get('reduzir_agora'))}",
            f"- Divida ajustada: R$ {divida_total:.2f}",
            f"- Reserva: R$ {reserva.get('atual', 0):.2f} de R$ {reserva.get('meta', 0):.2f}",
            f"- Limite seguro de credito disponivel: R$ {disponivel_seguro:.2f}",
            "",
            "Cartoes:",
            *cartoes_linhas[:5],
            "",
            "Lista de desejos em ordem de prioridade:",
            *desejos_linhas,
            "",
            "Proximas acoes:",
            *[f"- {a}" for a in proximas_acoes[:5]],
            "",
            "Regra: eu libero compra somente quando ela nao prejudicar conta, divida, reserva e plano de prosperidade.",
        ]

        return {
            "ok": True,
            "risco": risco,
            "decisao": decisao,
            "saldo_final": round(saldo_final, 2),
            "divida_total": round(divida_total, 2),
            "limite_seguro_disponivel": round(disponivel_seguro, 2),
            "saldo_utilizacao": uso_saldo,
            "desejos_priorizados": desejos_linhas,
            "proximas_acoes": proximas_acoes,
            "mensagem": "\n".join(linhas),
        }

    def decisao_compra(
        self,
        produto,
        valor=None,
        parcelas=None,
        salvar_desejo=False,
        urgencia=None,
        prazo_compra_meses=None,
        motivo_urgencia=None,
    ):
        from models.database import Desejo
        from services.ai_service import FinancialTools
        from services.wishlist_advisor_service import WishlistAdvisorService, classificar_prioridade

        produto = (produto or "").strip() or "item"
        valor = float(valor or 0)
        parcelas = int(parcelas or 1)
        parcelas = max(parcelas, 1)
        prazo_compra_meses = int(prazo_compra_meses or 0)

        wishlist = WishlistAdvisorService(self.db)
        tools = FinancialTools(self.db)

        if valor <= 0:
            diag = wishlist.diagnostico_compra(produto, None)
            valor = float(diag.get("preco") or 0)
        else:
            diag = wishlist.diagnostico_compra(produto, valor)

        analise_parcelas = tools.analisar_compra_parcelada(produto, valor, parcelas) if valor > 0 else None

        desejo = None
        plano_acao = None
        if salvar_desejo and valor > 0:
            desejo = self.db.query(Desejo).filter(Desejo.nome.ilike(produto)).first()
            if not desejo:
                desejo = Desejo(nome=produto, valor=valor, prioridade=classificar_prioridade(produto))
                self.db.add(desejo)
            else:
                desejo.valor = valor
                desejo.prioridade = desejo.prioridade or classificar_prioridade(produto)
            self.db.commit()
            plano_acao = wishlist.plano_acao_desejo(
                desejo,
                prazo_meses=prazo_compra_meses,
                urgencia=urgencia,
                parcelas=parcelas,
                motivo_urgencia=motivo_urgencia,
                salvar=True,
            )

        decisao = diag.get("decisao", "AGUARDAR_PLANEJANDO")
        if valor <= 0:
            titulo = "PRECISO DO VALOR"
        elif decisao in ["PODE_PLANEJAR", "PARCELADO_COM_CONTROLE"]:
            titulo = "PODE PLANEJAR COM CONTROLE"
        else:
            titulo = "NAO COMPRAR AGORA"

        linhas = [
            "Aurum Capital - central de decisao de compra",
            "",
            f"Decisao: {titulo}",
            f"Item: {produto}",
            f"Valor analisado: {self._moeda(valor)}",
            f"Prioridade: {(diag.get('prioridade') or 'media').upper()}",
            f"Melhor caminho: {diag.get('melhor_caminho')}",
            f"Quando comprar: {diag.get('quando_comprar')}",
        ]

        if analise_parcelas:
            linhas += [
                "",
                "Parcelamento:",
                f"- Simulacao: {parcelas}x de {self._moeda(analise_parcelas.get('valor_parcela'))}",
                f"- Fatura estimada com compra: {self._moeda(analise_parcelas.get('fatura_mes_estimada_com_compra'))}",
                f"- Limite seguro da parcela: {self._moeda(analise_parcelas.get('limite_parcela_segura'))}",
                f"- Recomendacao tecnica: {analise_parcelas.get('recomendacao')}",
            ]

        motivos = list(diag.get("motivos") or [])
        if analise_parcelas:
            motivos.extend(analise_parcelas.get("motivos") or [])
        if motivos:
            linhas.append("")
            linhas.append("Motivos:")
            linhas.extend([f"- {m}" for m in motivos[:6]])

        if desejo:
            linhas.append("")
            linhas.append("Item salvo/atualizado na lista de desejos para eu acompanhar o preco e te avisar no momento certo.")
        if plano_acao:
            linhas.append("")
            linhas.append("Plano de acao salvo no desejo:")
            if plano_acao.get("prazo_compra_meses"):
                linhas.append(f"- Prazo alvo: {plano_acao['prazo_compra_meses']} mes(es)")
            else:
                linhas.append("- Prazo alvo: sem prazo fixo; liberar somente quando a base financeira estiver saudavel")
            linhas.append(f"- Forma recomendada: {plano_acao['forma_recomendada']}")
            if plano_acao.get("parcelas_recomendadas"):
                linhas.append(f"- Parcelamento: {plano_acao['parcelas_recomendadas']}x de {self._moeda(plano_acao.get('valor_parcela_recomendado'))}")
            linhas.append(f"- Guardar antes da compra: {self._moeda(plano_acao.get('aporte_pre_compra_mensal'))}/mes")

        linhas.append("")
        linhas.append("Proximo passo: se quiser, diga 'salvar esse item na lista de desejos' ou me mande outro valor/parcelas para simular.")

        return {
            "ok": True,
            "produto": produto,
            "valor": round(valor, 2),
            "parcelas": parcelas,
            "decisao": titulo,
            "diagnostico": diag,
            "analise_parcelas": analise_parcelas,
            "plano_acao": plano_acao,
            "salvo_desejo": bool(desejo),
            "mensagem": "\n".join(linhas),
        }

    def fechamento_mensal(self, mes_ref=None):
        from services.monthly_service import MonthlyService

        monthly = MonthlyService(self.db)
        mes_ref = mes_ref or datetime.now().strftime("%Y-%m")
        resumo = monthly.salvar_resumo_mes(mes_ref)

        mes_anterior = monthly._mes_anterior(mes_ref)
        historico = {row["mes_ref"]: row for row in monthly.historico(6)}
        anterior = historico.get(mes_anterior)

        saldo_final = float(resumo.get("saldo_final") or 0)
        movimento = float(resumo.get("movimento_mes") or 0)
        divida = float(resumo.get("divida_ajustada") or 0)

        comparativos = []
        if anterior:
            delta_saldo = saldo_final - float(anterior.get("saldo_final") or 0)
            delta_gastos = float(resumo.get("gastos_mes") or 0) - float(anterior.get("gastos_mes") or 0)
            delta_divida = divida - float(anterior.get("divida_ajustada") or 0)
            comparativos = [
                f"Saldo final vs mes anterior: {self._moeda(delta_saldo)}",
                f"Gastos vs mes anterior: {self._moeda(delta_gastos)}",
                f"Divida ajustada vs mes anterior: {self._moeda(delta_divida)}",
            ]
        else:
            comparativos = ["Ainda nao ha mes anterior salvo para comparar. Este fechamento vira a nova base."]

        if saldo_final < 0:
            decisao = "Mes fechou em risco. Prioridade total: recompor saldo e congelar desejos."
        elif divida > 0:
            decisao = "Mes fechou positivo, mas ainda existe divida. Direcione a sobra para reduzir pendencias."
        elif movimento > 0:
            decisao = "Mes fechou saudavel. Pode separar aporte para reserva/investimento antes de liberar desejos."
        else:
            decisao = "Mes ficou apertado. Ajuste limites antes de assumir novas parcelas."

        uso_saldo = self.saldo_utilizacao()
        ranking = []
        try:
            from services.wishlist_advisor_service import WishlistAdvisorService
            ranking = WishlistAdvisorService(self.db).ranking_inteligente(5)
        except Exception:
            ranking = []

        linhas = [
            "Aurum Capital - fechamento mensal",
            "",
            f"Mes: {mes_ref}",
            f"Decisao: {decisao}",
            "",
            "Resumo:",
            f"- Saldo inicial: {self._moeda(resumo.get('saldo_inicial'))}",
            f"- Receita total: {self._moeda(resumo.get('receita_total'))}",
            f"- Contas pendentes: {self._moeda(resumo.get('contas_pendentes'))}",
            f"- Gastos do mes: {self._moeda(resumo.get('gastos_mes'))}",
            f"- Parcelas do mes: {self._moeda(resumo.get('parcelas_mes'))}",
            f"- Movimento do mes: {self._moeda(movimento)}",
            f"- Saldo final: {self._moeda(saldo_final)}",
            f"- Divida ajustada: {self._moeda(divida)}",
            "",
            "Comparativo:",
            *[f"- {c}" for c in comparativos],
            "",
            "Uso seguro daqui para frente:",
            f"- {uso_saldo.get('mensagem_curta')}",
            f"- {uso_saldo.get('orientacao')}",
        ]

        if ranking:
            linhas += [
                "",
                "Desejos para revisar no proximo mes:",
                *[
                    f"- {item['nome']}: {item['decisao']} | {item['melhor_caminho']}"
                    for item in ranking[:5]
                ],
            ]

        return {
            "ok": True,
            "mes_ref": mes_ref,
            "resumo": resumo,
            "comparativos": comparativos,
            "decisao": decisao,
            "ranking_desejos": ranking,
            "mensagem": "\n".join(linhas),
        }
