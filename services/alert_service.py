from datetime import datetime, date, timedelta
import calendar
import requests
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN nao configurado"
    try:
        r = requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=20,
        )
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

class AlertService:
    def __init__(self, db_session, send_fn=None):
        self.db = db_session
        self._send_fn = send_fn or telegram_send

    def verificar_todos_alertas(self, chat_id):
        alertas_enviados = []
        alertas_enviados.extend(self._alerta_contas_vencimento(chat_id))
        alertas_enviados.extend(self._alerta_limite_categoria(chat_id))
        alertas_enviados.extend(self._alerta_reserva(chat_id))
        alertas_enviados.extend(self._alerta_divida(chat_id))
        alertas_enviados.extend(self._alerta_saldo_negativo(chat_id))
        return alertas_enviados

    def _alerta_contas_vencimento(self, chat_id):
        from models.database import ContaFixa

        hoje = date.today()
        contas = self.db.query(ContaFixa).filter(ContaFixa.pago == False).all()
        alertas = []

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

            if dias_uteis in [1, 2, 3]:
                emoji = "URGENTE" if dias_uteis == 1 else "ATENCAO"
                tipo_dia = "dia util" if dias_uteis == 1 else "dias uteis"
                msg = (
                    emoji + " - ALERTA DE VENCIMENTO\n"
                    "Conta: " + c.nome.upper() + "\n"
                    "Valor: R$ " + str(round(c.valor, 2)) + "\n"
                    "Vence em: " + str(dias_uteis) + " " + tipo_dia + "\n"
                    "Data: " + venc.strftime('%d/%m/%Y') + "\n\n"
                    "Nao deixe atrasar!"
                )
                telegram_send(chat_id, msg)
                alertas.append("conta_" + c.nome)

        return alertas

    def _alerta_limite_categoria(self, chat_id):
        from models.database import Limite, Lancamento

        mes_atual = datetime.now().strftime("%Y-%m")
        limites = self.db.query(Limite).all()
        alertas = []

        for lim in limites:
            gastos = self.db.query(Lancamento).filter(
                Lancamento.mes_ref == mes_atual,
                Lancamento.categoria == lim.categoria
            ).all()
            total = sum(l.valor for l in gastos)
            percentual = (total / lim.valor) * 100 if lim.valor > 0 else 0

            if percentual >= 100:
                msg = (
                    "LIMITE ESTOURADO!\n"
                    "Categoria: " + lim.categoria.upper() + "\n"
                    "Limite: R$ " + str(round(lim.valor, 2)) + "\n"
                    "Gasto: R$ " + str(round(total, 2)) + "\n"
                    "Excesso: R$ " + str(round(total - lim.valor, 2)) + "\n\n"
                    "Cuidado! Voce esta gastando alem do planejado."
                )
                telegram_send(chat_id, msg)
                alertas.append("limite_" + lim.categoria)
            elif percentual >= 80:
                msg = (
                    "ALERTA DE LIMITE\n"
                    "Categoria: " + lim.categoria.upper() + "\n"
                    "Usado: " + str(round(percentual, 0)) + "% (R$ " + str(round(total, 2)) + " de R$ " + str(round(lim.valor, 2)) + ")\n\n"
                    "Voce esta perto do limite. Segure os gastos!"
                )
                telegram_send(chat_id, msg)
                alertas.append("limite80_" + lim.categoria)

        return alertas

    def _alerta_reserva(self, chat_id):
        from models.database import Config

        config = self.db.query(Config).first()
        if not config:
            return []

        atual = config.reserva_atual or 0
        meta = config.meta_reserva or 12000

        if meta > 0 and atual < meta:
            percentual = (atual / meta) * 100
            if datetime.now().day in [1, 15] and percentual < 50:
                msg = (
                    "LEMBRETE DE RESERVA\n"
                    "Meta: R$ " + str(round(meta, 2)) + "\n"
                    "Atual: R$ " + str(round(atual, 2)) + " (" + str(round(percentual, 1)) + "%)\n"
                    "Faltante: R$ " + str(round(meta - atual, 2)) + "\n\n"
                    "Sua reserva de emergencia esta baixa.\n"
                    "Tente guardar pelo menos R$ " + str(round((meta - atual) / 12, 2)) + " este mes."
                )
                telegram_send(chat_id, msg)
                return ["reserva_baixa"]

        return []

    def _alerta_divida(self, chat_id):
        from models.database import Divida

        dividas = self.db.query(Divida).all()
        total = sum(d.valor for d in dividas)

        if total > 0 and datetime.now().day in [5, 15, 25]:
            primeiro = dividas[0] if dividas else None
            nome_primeiro = primeiro.nome.upper() if primeiro else "-"
            valor_primeiro = str(round(primeiro.valor, 2)) if primeiro else "0"
            msg = (
                "CHECK-UP DE DIVIDAS\n"
                "Total pendente: R$ " + str(round(total, 2)) + "\n"
                "Proximo na lista: " + nome_primeiro + " - R$ " + valor_primeiro + "\n\n"
                "Meta do mes: R$ " + str(round(total / 3, 2)) + "\n"
                "Qualquer renda extra deve ir para ca primeiro!"
            )
            telegram_send(chat_id, msg)
            return ["divida_checkup"]

        return []

    def _alerta_saldo_negativo(self, chat_id):
        from services.ai_service import FinancialTools

        tools = FinancialTools(self.db)
        saldo = tools.get_saldo_atual()

        saldo_final = saldo.get("saldo_final", saldo["saldo_projetado"])
        if saldo_final < 0:
            msg = (
                "ATENCAO: SALDO FINAL NEGATIVO\n\n"
                "Seu saldo final esta em R$ " + str(round(saldo_final, 2)) + "\n"
                "Isso significa que voce vai ficar no vermelho antes do fim do mes.\n\n"
                "Acoes imediatas:\n"
                "- Segure gastos nao essenciais\n"
                "- Priorize contas que vencem primeiro\n"
                "- Se possivel, gere renda extra\n\n"
                "Posso ajudar a reorganizar seu orcamento?"
            )
            telegram_send(chat_id, msg)
            return ["saldo_negativo"]

        return []

    def alerta_mensal_pdf(self, chat_id, pdf_url):
        msg = (
            "RELATORIO MENSAL GERADO\n\n"
            "O relatorio financeiro do mes esta pronto!\n\n"
            "Baixe aqui: " + pdf_url + "\n\n"
            "Dica: Guarde os relatorios mensais para acompanhar sua evolucao financeira."
        )
        telegram_send(chat_id, msg)
