import math


class GoalPlannerService:
    """Detailed conquest planning for big goals such as a home."""

    def __init__(self, db_session):
        self.db = db_session

    def _moeda(self, valor):
        valor = float(valor or 0)
        sinal = "-R$ " if valor < 0 else "R$ "
        texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return sinal + texto

    def _aporte_com_retorno(self, valor_meta, meses, retorno_anual_pct):
        valor_meta = max(float(valor_meta or 0), 0)
        meses = max(int(meses or 1), 1)
        retorno_anual_pct = max(float(retorno_anual_pct or 0), 0)
        taxa_mensal = ((1 + retorno_anual_pct / 100) ** (1 / 12)) - 1
        if taxa_mensal <= 0:
            return valor_meta / meses
        fator = (((1 + taxa_mensal) ** meses - 1) / taxa_mensal)
        return valor_meta / fator if fator > 0 else valor_meta / meses

    def _meses_para_juntar(self, valor, aporte):
        valor = max(float(valor or 0), 0)
        aporte = max(float(aporte or 0), 0)
        if valor <= 0:
            return 0
        if aporte <= 0:
            return None
        return math.ceil(valor / aporte)

    def _tem_veiculo(self):
        from models.database import ContaFixa, Divida

        termos = ["carro", "veiculo", "ipva", "seguro auto", "financiamento auto"]
        contas = " ".join([(c.nome or "").lower() for c in self.db.query(ContaFixa).all()])
        dividas = " ".join([(d.nome or "").lower() for d in self.db.query(Divida).all()])
        texto = contas + " " + dividas
        return any(t in texto for t in termos)

    def plano_conquista(
        self,
        valor_meta=600000,
        prazo_anos=10,
        retorno_anual_pct=6,
        entrada_pct=20,
        documentacao_pct=5,
        tipo="casa",
    ):
        from services.ai_service import FinancialTools

        tools = FinancialTools(self.db)
        saldo = tools.get_saldo_atual()
        dividas = tools.get_analise_dividas()
        reserva = tools.get_reserva_status()
        visao = tools.get_visao_patrimonial()

        valor_meta = max(float(valor_meta or 600000), 0)
        prazo_anos = max(float(prazo_anos or 10), 0.25)
        meses = max(int(round(prazo_anos * 12)), 1)
        entrada_pct = max(float(entrada_pct or 20), 0)
        documentacao_pct = max(float(documentacao_pct or 5), 0)

        renda = float(saldo.get("receita_total") or 0)
        saldo_final = float(saldo.get("saldo_final", saldo.get("saldo_projetado", 0)) or 0)
        contas = float(saldo.get("contas_pendentes") or 0)
        parcelas = float(saldo.get("parcelas_mes") or 0)
        gastos = float(saldo.get("gastos_mes") or 0)
        divida_total = float(dividas.get("total_divida") or 0)
        reserva_atual = float(reserva.get("atual") or 0)
        reserva_config = float(reserva.get("meta") or 0)
        capacidade = max(float(visao.get("aporte_mensal_sugerido") or 0), 0)

        custo_essencial_mensal = max(contas + parcelas + min(gastos, renda * 0.35), renda * 0.45, 1)
        reserva_ideal = max(reserva_config, custo_essencial_mensal * 6)
        falta_reserva = max(reserva_ideal - reserva_atual, 0)

        fundo_roupa = max(renda * 0.20, 800)
        fundo_veiculo = max(renda * (0.60 if self._tem_veiculo() else 0.35), 1800)
        recompor_saldo = max(abs(saldo_final), 0) if saldo_final < 0 else 0

        entrada = valor_meta * (entrada_pct / 100)
        documentacao = valor_meta * (documentacao_pct / 100)
        alvo_entrada = entrada + documentacao
        fundacao_total = recompor_saldo + divida_total + falta_reserva + fundo_roupa + fundo_veiculo
        alvo_primeira_conquista = fundacao_total + alvo_entrada

        aporte_necessario_primeira = self._aporte_com_retorno(alvo_primeira_conquista, meses, retorno_anual_pct)
        aporte_necessario_a_vista = self._aporte_com_retorno(valor_meta + documentacao, meses, retorno_anual_pct)
        gap_mensal = aporte_necessario_primeira - capacidade
        meses_estimados_primeira = self._meses_para_juntar(alvo_primeira_conquista, capacidade)

        etapas = [
            {
                "ordem": 1,
                "nome": "Recompor saldo do mes",
                "alvo": round(recompor_saldo, 2),
                "atual": 0,
                "falta": round(recompor_saldo, 2),
                "essencial": True,
                "motivo": "Antes de sonhar grande, o mes precisa fechar no azul.",
            },
            {
                "ordem": 2,
                "nome": "Quitar/reduzir dividas",
                "alvo": round(divida_total, 2),
                "atual": 0,
                "falta": round(divida_total, 2),
                "essencial": True,
                "motivo": "Divida cara normalmente atrasa mais do que investimento ajuda.",
            },
            {
                "ordem": 3,
                "nome": "Reserva de emergencia",
                "alvo": round(reserva_ideal, 2),
                "atual": round(reserva_atual, 2),
                "falta": round(falta_reserva, 2),
                "essencial": True,
                "motivo": "Protege casa, familia, saude e renda antes de assumir parcela grande.",
            },
            {
                "ordem": 4,
                "nome": "Fundo de roupas e necessidades",
                "alvo": round(fundo_roupa, 2),
                "atual": 0,
                "falta": round(fundo_roupa, 2),
                "essencial": True,
                "motivo": "Roupa, calcado e itens basicos nao devem virar cartao por falta de planejamento.",
            },
            {
                "ordem": 5,
                "nome": "Fundo de veiculo/manutencao",
                "alvo": round(fundo_veiculo, 2),
                "atual": 0,
                "falta": round(fundo_veiculo, 2),
                "essencial": True,
                "motivo": "IPVA, pneus, seguro e manutencao precisam de dinheiro separado.",
            },
            {
                "ordem": 6,
                "nome": f"Entrada e documentos da {tipo}",
                "alvo": round(alvo_entrada, 2),
                "atual": 0,
                "falta": round(alvo_entrada, 2),
                "essencial": False,
                "motivo": f"Entrada de {entrada_pct:.0f}% mais {documentacao_pct:.0f}% para custos de compra.",
            },
        ]

        plano_mensal = self._plano_mensal(capacidade, etapas)
        parcela_habitacao_segura = round(renda * 0.25, 2)
        renda_minima_para_parcela = round((parcela_habitacao_segura / 0.25), 2) if parcela_habitacao_segura > 0 else 0

        cenarios = {
            "entrada_financiamento": {
                "alvo": round(alvo_entrada, 2),
                "aporte_mensal_necessario": round(self._aporte_com_retorno(alvo_entrada, meses, retorno_anual_pct), 2),
                "parcela_habitacao_segura": parcela_habitacao_segura,
                "leitura": "Financiamento so entra depois da fundacao pronta e com parcela habitacional dentro de ate 25% da renda.",
            },
            "carta_credito": {
                "alvo_lance_recomendado": round(entrada, 2),
                "documentacao_fora_da_carta": round(documentacao, 2),
                "alvo_total_antes_da_contemplacao": round(entrada + documentacao + fundacao_total, 2),
                "leitura": "Carta de credito pode ser caminho se voce aceita esperar contemplacao e nao compromete a reserva. Simule taxa/administradora fora do app antes de contratar.",
            },
            "compra_a_vista": {
                "alvo": round(valor_meta + documentacao, 2),
                "aporte_mensal_necessario": round(aporte_necessario_a_vista, 2),
                "leitura": "Compra a vista exige mais tempo, mas reduz risco de parcela longa.",
            },
        }

        if capacidade <= 0:
            leitura = "Hoje a renda cadastrada ainda nao mostra sobra segura. Primeiro calibre renda, saldo, contas e corte vazamentos antes da meta."
        elif gap_mensal <= 0:
            leitura = "A primeira conquista cabe no ritmo atual se voce seguir a ordem: base de seguranca primeiro, casa depois."
        else:
            leitura = f"Para cumprir o prazo, faltam {self._moeda(gap_mensal)}/mes. Caminhos: aumentar renda, alongar prazo, reduzir valor do imovel ou cortar gastos."

        linhas = [
            "Aurum Capital - plano de conquista",
            "",
            f"Objetivo: {tipo} de {self._moeda(valor_meta)}",
            f"Prazo desejado: {prazo_anos:g} anos",
            f"Renda cadastrada: {self._moeda(renda)}",
            f"Aporte mensal seguro hoje: {self._moeda(capacidade)}",
            "",
            "Valor exato para chegar na primeira fase segura:",
            f"- Fundacao financeira: {self._moeda(fundacao_total)}",
            f"- Entrada + documentos: {self._moeda(alvo_entrada)}",
            f"- Total antes de assumir a casa: {self._moeda(alvo_primeira_conquista)}",
            f"- Aporte necessario no prazo: {self._moeda(aporte_necessario_primeira)}/mes",
            f"- Gap mensal: {self._moeda(max(gap_mensal, 0))}",
            f"- Parcela habitacional segura hoje: ate {self._moeda(parcela_habitacao_segura)}/mes",
            "",
            "Ordem do dinheiro:",
        ]
        for etapa in etapas:
            if etapa["falta"] > 0:
                linhas.append(f"{etapa['ordem']}. {etapa['nome']}: falta {self._moeda(etapa['falta'])}. {etapa['motivo']}")
        linhas += [
            "",
            "Plano mensal recomendado agora:",
            *[f"- {item['destino']}: {self._moeda(item['valor'])}/mes" for item in plano_mensal],
            "",
            "Ideias de caminho:",
            f"- Entrada/financiamento: juntar {self._moeda(alvo_entrada)} antes de assumir parcela.",
            f"- Carta de credito: ter pelo menos {self._moeda(entrada + documentacao + fundacao_total)} entre fundacao, lance e documentos; parcela acima de {self._moeda(parcela_habitacao_segura)}/mes fica perigosa hoje.",
            f"- A vista: mirar {self._moeda(valor_meta + documentacao)}.",
            "",
            leitura,
            "Observacao: os percentuais sao simulacao educativa. Antes de contratar financiamento, carta ou consorcio, compare CET, taxa administrativa, prazo e regras do contrato.",
        ]

        return {
            "ok": True,
            "tipo": tipo,
            "valor_meta": round(valor_meta, 2),
            "prazo_anos": prazo_anos,
            "meses": meses,
            "renda_total": round(renda, 2),
            "saldo_final": round(saldo_final, 2),
            "capacidade_mensal_atual": round(capacidade, 2),
            "custo_essencial_mensal": round(custo_essencial_mensal, 2),
            "reserva_ideal": round(reserva_ideal, 2),
            "fundacao_total": round(fundacao_total, 2),
            "entrada_recomendada": round(entrada, 2),
            "documentacao_estimada": round(documentacao, 2),
            "alvo_entrada_documentos": round(alvo_entrada, 2),
            "alvo_primeira_conquista": round(alvo_primeira_conquista, 2),
            "aporte_mensal_necessario": round(aporte_necessario_primeira, 2),
            "gap_mensal": round(gap_mensal, 2),
            "meses_estimados_primeira_conquista": meses_estimados_primeira,
            "parcela_habitacao_segura": parcela_habitacao_segura,
            "renda_minima_para_parcela": renda_minima_para_parcela,
            "etapas": etapas,
            "plano_mensal": plano_mensal,
            "cenarios": cenarios,
            "leitura": leitura,
            "mensagem": "\n".join(linhas),
        }

    def _plano_mensal(self, capacidade, etapas):
        capacidade = round(max(float(capacidade or 0), 0), 2)
        if capacidade <= 0:
            return [{"destino": "Ajustar orcamento ate criar sobra", "valor": 0, "motivo": "Sem sobra segura nao existe aporte real."}]

        abertas = [e for e in etapas if e.get("falta", 0) > 0]
        if not abertas:
            return [{"destino": "Investir para patrimonio", "valor": capacidade, "motivo": "Fundacao completa."}]

        primeira = abertas[0]
        if primeira["ordem"] <= 2:
            return [{"destino": primeira["nome"], "valor": capacidade, "motivo": primeira["motivo"]}]

        if primeira["ordem"] <= 5:
            reserva = next((e for e in abertas if e["ordem"] == 3), None)
            roupas = next((e for e in abertas if e["ordem"] == 4), None)
            veiculo = next((e for e in abertas if e["ordem"] == 5), None)
            plano = []
            if reserva:
                plano.append({"destino": reserva["nome"], "valor": round(capacidade * 0.70, 2), "motivo": reserva["motivo"]})
            if roupas:
                plano.append({"destino": roupas["nome"], "valor": round(capacidade * 0.10, 2), "motivo": roupas["motivo"]})
            if veiculo:
                plano.append({"destino": veiculo["nome"], "valor": round(capacidade * 0.20, 2), "motivo": veiculo["motivo"]})
            return [p for p in plano if p["valor"] > 0] or [{"destino": primeira["nome"], "valor": capacidade, "motivo": primeira["motivo"]}]

        return [
            {"destino": primeira["nome"], "valor": round(capacidade * 0.85, 2), "motivo": primeira["motivo"]},
            {"destino": "Reserva de oportunidade", "valor": round(capacidade * 0.15, 2), "motivo": "Mantem flexibilidade para imprevistos e boas oportunidades."},
        ]
