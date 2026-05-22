import os


class AdvisorService:
    def __init__(self, db_session):
        self.db = db_session

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

    def checkup_patrimonial(self, limite_desejos=6):
        from models.database import Desejo
        from services.ai_service import FinancialTools
        from services.card_limit_service import CardLimitService
        from services.wishlist_advisor_service import WishlistAdvisorService

        tools = FinancialTools(self.db)
        saldo = tools.get_saldo_atual()
        dividas = tools.get_analise_dividas()
        reserva = tools.get_reserva_status()
        visao = tools.get_visao_patrimonial()
        limites = CardLimitService(self.db).resumo_limites()
        wishlist = WishlistAdvisorService(self.db)

        saldo_final = saldo.get("saldo_final", saldo.get("saldo_projetado", 0)) or 0
        divida_total = dividas.get("total_divida", 0) or 0
        reserva_faltante = reserva.get("faltante", 0) or 0
        disponivel_seguro = limites.get("disponivel_seguro_mes", 0) or 0

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
        desejos.sort(key=lambda d: (prioridade_rank.get((d.prioridade or "media").lower(), 2), d.valor or 0))

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
            "desejos_priorizados": desejos_linhas,
            "proximas_acoes": proximas_acoes,
            "mensagem": "\n".join(linhas),
        }
