from datetime import datetime, date, timedelta
import calendar
import requests
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN não configurado"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=20,
        )
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

class AlertService:
    def __init__(self, db_session):
        self.db = db_session

    def verificar_todos_alertas(self, chat_id: str):
        """Verifica e envia todos os alertas pendentes"""
        alertas_enviados = []

        # 1. Alerta de contas próximas do vencimento
        alertas_enviados.extend(self._alerta_contas_vencimento(chat_id))

        # 2. Alerta de limite de categoria estourado
        alertas_enviados.extend(self._alerta_limite_categoria(chat_id))

        # 3. Alerta de meta de reserva
        alertas_enviados.extend(self._alerta_reserva(chat_id))

        # 4. Alerta de dívida
        alertas_enviados.extend(self._alerta_divida(chat_id))

        # 5. Alerta de saldo negativo projetado
        alertas_enviados.extend(self._alerta_saldo_negativo(chat_id))

        return alertas_enviados

    def _alerta_contas_vencimento(self, chat_id: str):
        from models.database import ContaFixa
        from services.ai_service import FinancialTools

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
                emoji = "🚨" if dias_uteis == 1 else "⚠️"
                msg = (
                    f"{emoji} ALERTA DE VENCIMENTO
"
                    f"Conta: {c.nome.upper()}
"
                    f"Valor: R$ {c.valor:.2f}
"
                    f"Vence em: {dias_uteis} {'dia útil' if dias_uteis == 1 else 'dias úteis'}
"
                    f"📅 Data: {venc.strftime('%d/%m/%Y')}

"
                    f"Não deixe atrasar!"
                )
                telegram_send(chat_id, msg)
                alertas.append(f"conta_{c.nome}")

        return alertas

    def _alerta_limite_categoria(self, chat_id: str):
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
                    f"🛑 LIMITE ESTOURADO!
"
                    f"Categoria: {lim.categoria.upper()}
"
                    f"Limite: R$ {lim.valor:.2f}
"
                    f"Gasto: R$ {total:.2f}
"
                    f"Excesso: R$ {total - lim.valor:.2f}

"
                    f"⚠️ Cuidado! Você está gastando além do planejado."
                )
                telegram_send(chat_id, msg)
                alertas.append(f"limite_{lim.categoria}")
            elif percentual >= 80:
                msg = (
                    f"⚡ ALERTA DE LIMITE
"
                    f"Categoria: {lim.categoria.upper()}
"
                    f"Usado: {percentual:.0f}% (R$ {total:.2f} de R$ {lim.valor:.2f})

"
                    f"💡 Você está perto do limite. Segure os gastos!"
                )
                telegram_send(chat_id, msg)
                alertas.append(f"limite80_{lim.categoria}")

        return alertas

    def _alerta_reserva(self, chat_id: str):
        from models.database import Config

        config = self.db.query(Config).first()
        if not config:
            return []

        atual = config.reserva_atual or 0
        meta = config.meta_reserva or 12000

        if meta > 0 and atual < meta:
            percentual = (atual / meta) * 100

            # Alerta semanal (dia 1 de cada semana)
            if datetime.now().day in [1, 15] and percentual < 50:
                msg = (
                    f"🏦 LEMBRETE DE RESERVA
"
                    f"Meta: R$ {meta:.2f}
"
                    f"Atual: R$ {atual:.2f} ({percentual:.1f}%)
"
                    f"Faltante: R$ {meta - atual:.2f}

"
                    f"📌 Sua reserva de emergência está baixa.
"
                    f"Tente guardar pelo menos R$ {(meta - atual)/12:.2f} este mês."
                )
                telegram_send(chat_id, msg)
                return ["reserva_baixa"]

        return []

    def _alerta_divida(self, chat_id: str):
        from models.database import Divida

        dividas = self.db.query(Divida).all()
        total = sum(d.valor for d in dividas)

        if total > 0 and datetime.now().day in [5, 15, 25]:
            msg = (
                f"💳 CHECK-UP DE DÍVIDAS
"
                f"Total pendente: R$ {total:.2f}
"
                f"Próximo na lista: {dividas[0].nome.upper()} - R$ {dividas[0].valor:.2f}

"
                f"🎯 Meta do mês: R$ {total/3:.2f}
"
                f"Qualquer renda extra deve ir para cá primeiro!"
            )
            telegram_send(chat_id, msg)
            return ["divida_checkup"]

        return []

    def _alerta_saldo_negativo(self, chat_id: str):
        from services.ai_service import FinancialTools

        tools = FinancialTools(self.db)
        saldo = tools.get_saldo_atual()

        if saldo["saldo_projetado"] < 0:
            msg = (
                f"🚨 ATENÇÃO: SALDO NEGATIVO PROJETADO

"
                f"Seu saldo projetado está em R$ {saldo['saldo_projetado']:.2f}
"
                f"Isso significa que você vai ficar no vermelho antes do fim do mês.

"
                f"💡 Ações imediatas:
"
                f"• Segure gastos não essenciais
"
                f"• Priorize contas que vencem primeiro
"
                f"• Se possível, gere renda extra

"
                f"Posso ajudar a reorganizar seu orçamento?"
            )
            telegram_send(chat_id, msg)
            return ["saldo_negativo"]

        return []

    def alerta_mensal_pdf(self, chat_id: str, pdf_url: str):
        """Envia alerta de relatório mensal gerado"""
        msg = (
            f"📊 RELATÓRIO MENSAL GERADO

"
            f"O relatório financeiro do mês está pronto!

"
            f"📄 Baixe aqui: {pdf_url}

"
            f"💡 Dica: Guarde os relatórios mensais para acompanhar sua evolução financeira."
        )
        telegram_send(chat_id, msg)
