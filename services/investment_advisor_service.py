from datetime import datetime


DEFAULT_INVESTMENT_TICKERS = [
    "^BVSP",
    "^GSPC",
    "^IXIC",
    "USDBRL=X",
    "BOVA11.SA",
    "IVVB11.SA",
    "SMAL11.SA",
    "ITUB4.SA",
    "BBAS3.SA",
    "BBDC4.SA",
    "SANB11.SA",
    "WEGE3.SA",
    "VALE3.SA",
    "PETR4.SA",
]


ASSET_PROFILE = {
    "^BVSP": ("referencia", "Ibovespa", "termometro da bolsa brasileira", "alto"),
    "^GSPC": ("referencia", "S&P 500", "termometro das maiores empresas dos EUA", "medio"),
    "^IXIC": ("referencia", "Nasdaq", "termometro de tecnologia nos EUA", "alto"),
    "USDBRL=X": ("referencia", "Dolar", "protege contra risco Brasil, mas oscila forte", "medio"),
    "BOVA11.SA": ("etf", "BOVA11", "ETF amplo de bolsa brasileira", "alto"),
    "IVVB11.SA": ("etf", "IVVB11", "ETF dolarizado ligado ao S&P 500", "medio"),
    "SMAL11.SA": ("etf", "SMAL11", "ETF de empresas menores brasileiras", "muito_alto"),
    "ITUB4.SA": ("acao_banco", "Itau", "banco privado grande e lucrativo", "medio"),
    "BBAS3.SA": ("acao_banco", "Banco do Brasil", "banco com dividendos e risco estatal", "medio"),
    "BBDC4.SA": ("acao_banco", "Bradesco", "banco privado em fase de recuperacao operacional", "medio"),
    "SANB11.SA": ("acao_banco", "Santander Brasil", "banco com foco em dividendos e ciclo de credito", "medio"),
    "WEGE3.SA": ("acao", "WEG", "empresa de qualidade, crescimento e preco normalmente exigente", "alto"),
    "VALE3.SA": ("acao", "Vale", "mineradora ciclica ligada a China e commodities", "muito_alto"),
    "PETR4.SA": ("acao", "Petrobras", "petroleira de dividendos, commodity e risco politico", "muito_alto"),
}


class InvestmentAdvisorService:
    def __init__(self, db_session):
        self.db = db_session

    def _moeda(self, valor):
        valor = float(valor or 0)
        texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {texto}"

    def _pct(self, valor):
        if valor is None:
            return "-"
        return f"{float(valor):.2f}%".replace(".", ",")

    def analisar(self, tickers=None):
        from services.advisor_service import AdvisorService
        from services.ai_service import FinancialTools
        from services.market_service import MarketService

        tools = FinancialTools(self.db)
        saldo = tools.get_saldo_atual()
        dividas = tools.get_analise_dividas()
        reserva = tools.get_reserva_status()
        visao = tools.get_visao_patrimonial()
        uso_saldo = AdvisorService(self.db).saldo_utilizacao()
        radar = MarketService().snapshot(tickers or DEFAULT_INVESTMENT_TICKERS)

        ativos = [self._avaliar_ativo(a) for a in radar.get("ativos", [])]
        ativos_ok = [a for a in ativos if a.get("ok")]
        estudos = [a for a in ativos_ok if a.get("classe") in ["etf", "acao_banco", "acao"]]
        estudos.sort(key=lambda a: (a.get("pontuacao", 0), a.get("retorno_6m_pct") or -999), reverse=True)

        divida_total = float(dividas.get("total_divida") or 0)
        reserva_faltante = float(reserva.get("faltante") or 0)
        aporte = float(visao.get("aporte_mensal_sugerido") or 0)
        saldo_final = float(saldo.get("saldo_final", saldo.get("saldo_projetado", 0)) or 0)

        if divida_total > 0:
            fase = "defesa"
            decisao = "Nao acelerar acoes agora. Primeiro reduzir dividas e proteger caixa."
            perfil = "recuperacao"
            carteira = [
                {"classe": "Dividas caras", "percentual": 70, "valor_sugerido": round(aporte * 0.70, 2), "motivo": "maior retorno ajustado ao risco e parar juros contra voce."},
                {"classe": "Reserva imediata", "percentual": 30, "valor_sugerido": round(aporte * 0.30, 2), "motivo": "evitar voltar para cartao ou cheque especial."},
                {"classe": "Acoes/ETFs", "percentual": 0, "valor_sugerido": 0, "motivo": "apenas estudo ate a divida aliviar."},
            ]
        elif reserva_faltante > 0:
            fase = "reserva"
            decisao = "Montar reserva antes de tomar risco em acoes."
            perfil = "conservador"
            carteira = [
                {"classe": "Tesouro Selic/CDB liquidez diaria", "percentual": 80, "valor_sugerido": round(aporte * 0.80, 2), "motivo": "liquidez e seguranca para emergencia."},
                {"classe": "CDB/LCI/LCA com FGC", "percentual": 20, "valor_sugerido": round(aporte * 0.20, 2), "motivo": "renda fixa com prazo curto e risco controlado."},
                {"classe": "Acoes/ETFs", "percentual": 0, "valor_sugerido": 0, "motivo": "entrar so depois da reserva estar firme."},
            ]
        else:
            fase = "crescimento"
            decisao = "Pode investir com diversificacao, aportes mensais e limite de risco."
            perfil = "moderado"
            carteira = [
                {"classe": "Renda fixa pos-fixada", "percentual": 45, "valor_sugerido": round(aporte * 0.45, 2), "motivo": "base estavel e liquidez."},
                {"classe": "ETFs diversificados", "percentual": 35, "valor_sugerido": round(aporte * 0.35, 2), "motivo": "exposicao ampla sem depender de uma empresa."},
                {"classe": "Acoes individuais", "percentual": 15, "valor_sugerido": round(aporte * 0.15, 2), "motivo": "satellite de qualidade, com risco limitado."},
                {"classe": "Caixa de oportunidade", "percentual": 5, "valor_sugerido": round(aporte * 0.05, 2), "motivo": "comprar com calma em quedas fortes."},
            ]

        renda_fixa = self._renda_fixa(divida_total, reserva_faltante)
        proximos_passos = self._proximos_passos(fase, uso_saldo, divida_total, reserva_faltante)
        mensagem = self._mensagem(
            decisao=decisao,
            perfil=perfil,
            saldo_final=saldo_final,
            aporte=aporte,
            divida_total=divida_total,
            reserva=reserva,
            carteira=carteira,
            renda_fixa=renda_fixa,
            estudos=estudos[:6],
            proximos_passos=proximos_passos,
            radar_ok=radar.get("ok"),
        )

        return {
            "ok": True,
            "generated_at": datetime.utcnow().isoformat(),
            "fonte": radar.get("fonte"),
            "observacao": "Opiniao educativa baseada em dados disponiveis, nao ordem de compra nem promessa de retorno.",
            "decisao": decisao,
            "fase": fase,
            "perfil": perfil,
            "saldo_final": round(saldo_final, 2),
            "aporte_mensal_sugerido": round(aporte, 2),
            "divida_total": round(divida_total, 2),
            "reserva": reserva,
            "saldo_utilizacao": uso_saldo,
            "carteira_sugerida": carteira,
            "bancos_e_renda_fixa": renda_fixa,
            "acoes_para_estudo": estudos[:8],
            "radar": radar,
            "proximos_passos": proximos_passos,
            "mensagem": mensagem,
        }

    def _avaliar_ativo(self, ativo):
        row = dict(ativo)
        ticker = row.get("ticker")
        classe, nome_curto, tese, risco = ASSET_PROFILE.get(
            ticker,
            ("acao", ticker or "Ativo", "ativo para estudo", "alto"),
        )
        row.update({
            "classe": classe,
            "nome_curto": nome_curto,
            "tese": tese,
            "risco": risco,
            "pontuacao": 0,
            "leitura": "Cotacao indisponivel agora.",
        })
        if not row.get("ok"):
            return row

        score = 50
        ret30 = row.get("retorno_30d_pct")
        ret6m = row.get("retorno_6m_pct")
        if ret30 is not None:
            score += 10 if ret30 > 0 else -10
            if ret30 < -12:
                score -= 8
            if ret30 > 18:
                score -= 5
        if ret6m is not None:
            score += 15 if ret6m > 0 else -12
            if ret6m > 35:
                score -= 8
            if ret6m < -20:
                score -= 8
        if classe == "etf":
            score += 8
        if classe == "acao_banco":
            score += 5
        if risco == "muito_alto":
            score -= 8

        row["pontuacao"] = max(min(round(score, 1), 100), 0)
        if score >= 68:
            row["leitura"] = "forte para acompanhar, mas comprar so dentro da alocacao."
        elif score >= 52:
            row["leitura"] = "neutro para estudo; entrar aos poucos se fizer sentido."
        else:
            row["leitura"] = "exige paciencia; nao comprar por impulso."
        return row

    def _renda_fixa(self, divida_total, reserva_faltante):
        if divida_total > 0:
            prioridade = "Antes de procurar a melhor acao, quite dividas caras. Esse e o investimento com retorno mais claro."
        elif reserva_faltante > 0:
            prioridade = "Seu foco e reserva. Prefira liquidez diaria e baixo risco."
        else:
            prioridade = "Com reserva pronta, combine liquidez, prazo e um pouco de risco controlado."

        return [
            {
                "nome": "Reserva de emergencia",
                "onde": "Tesouro Selic ou CDB liquidez diaria de banco solido",
                "criterio": "liquidez diaria, baixo risco, sem travar dinheiro essencial",
                "prioridade": prioridade,
            },
            {
                "nome": "Renda fixa com FGC",
                "onde": "CDB, LCI ou LCA de bancos com pelo menos 100% do CDI",
                "criterio": "respeitar limite do FGC e prazo compativel com sua meta",
                "prioridade": "Boa para dinheiro que nao precisa sair amanha.",
            },
            {
                "nome": "Bancos para comparar",
                "onde": "Itau, Banco do Brasil, Bradesco, Santander e bancos digitais com liquidez diaria",
                "criterio": "comparar taxa, liquidez, garantia, imposto e vencimento",
                "prioridade": "A melhor taxa nao serve se prender o dinheiro que paga sua vida.",
            },
        ]

    def _proximos_passos(self, fase, uso_saldo, divida_total, reserva_faltante):
        passos = []
        if uso_saldo.get("reduzir_agora", 0) > 0:
            passos.append(f"Reduzir {self._moeda(uso_saldo.get('reduzir_agora'))} antes de qualquer aporte novo.")
        if divida_total > 0:
            passos.append("Usar aportes para atacar dividas por prioridade antes de comprar acoes.")
        elif reserva_faltante > 0:
            passos.append(f"Direcionar aportes para completar a reserva que ainda falta: {self._moeda(reserva_faltante)}.")
        else:
            passos.append("Definir aporte automatico mensal e rebalancear a carteira a cada mes.")
        if fase == "crescimento":
            passos.append("Comprar ETFs primeiro e limitar acoes individuais a uma parte pequena do patrimonio.")
        else:
            passos.append("Montar lista de estudos de acoes, mas executar compra so quando caixa e reserva estiverem saudaveis.")
        passos.append("Nunca concentrar tudo em uma acao, banco ou setor.")
        return passos

    def _mensagem(self, decisao, perfil, saldo_final, aporte, divida_total, reserva, carteira, renda_fixa, estudos, proximos_passos, radar_ok):
        linhas = [
            "Aurum Capital - analise de mercado e investimentos",
            "",
            f"Decisao: {decisao}",
            f"Perfil operacional agora: {perfil}",
            f"Saldo final projetado: {self._moeda(saldo_final)}",
            f"Aporte mensal possivel: {self._moeda(aporte)}",
            f"Divida ajustada: {self._moeda(divida_total)}",
            f"Reserva: {self._moeda(reserva.get('atual', 0))} de {self._moeda(reserva.get('meta', 0))}",
            "",
            "Carteira sugerida para a fase atual:",
        ]
        for item in carteira:
            linhas.append(f"- {item['classe']}: {item['percentual']}% ({self._moeda(item['valor_sugerido'])}/mes). {item['motivo']}")

        linhas.extend(["", "Bancos e renda fixa:"])
        for item in renda_fixa:
            linhas.append(f"- {item['nome']}: {item['onde']}. Criterio: {item['criterio']}")

        linhas.extend(["", "Acoes e ETFs para estudo:"])
        if radar_ok and estudos:
            for ativo in estudos[:6]:
                linhas.append(
                    f"- {ativo['ticker']} ({ativo['nome_curto']}): {self._moeda(ativo.get('preco'))} | "
                    f"30d {self._pct(ativo.get('retorno_30d_pct'))} | 6m {self._pct(ativo.get('retorno_6m_pct'))} | "
                    f"risco {ativo['risco']} | {ativo['leitura']}"
                )
        else:
            linhas.append("- Mercado indisponivel agora. Nao vou inventar cotacao; tente novamente depois.")

        linhas.extend(["", "Proximos passos:"])
        linhas.extend([f"- {p}" for p in proximos_passos])
        linhas.append("")
        linhas.append("Regra: opiniao de estudo e controle de risco. Nao e ordem de compra, promessa de retorno ou garantia.")
        return "\n".join(linhas)
