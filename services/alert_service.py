from datetime import datetime, date, timedelta
import calendar

class AlertService:
    def __init__(self, db_session, telegram_sender):
        self.db = db_session
        self.send_telegram = telegram_sender

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
                    f"{emoji} ALERTA DE VENCIMENTO\n"
                    f"Conta: {c.nome.upper()}\n"
                    f"Valor: R$ {c.valor:.2f}\n"
                    f"Vence em: {dias_uteis} {'dia útil' if dias_uteis == 1 else 'dias úteis'}\n"
                    f"📅 Data: {venc.strftime('%d/%m/%Y')}\n\n"
                    f"Não deixe atrasar!"
                )
                self.send_telegram(chat_id, msg)
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
                    f"🛑 LIMITE ESTOURADO!\n"
                    f"Categoria: {lim.categoria.upper()}\n"
                    f"Limite: R$ {lim.valor:.2f}\n"
                    f"Gasto: R$ {total:.2f}\n"
                    f"Excesso: R$ {total - lim.valor:.2f}\n\n"
                    f"⚠️ Cuidado! Você está gastando além do planejado."
                )
                self.send_telegram(chat_id, msg)
                alertas.append(f"limite_{lim.categoria}")
            elif percentual >= 80:
                msg = (
                    f"⚡ ALERTA DE LIMITE\n"
                    f"Categoria: {lim.categoria.upper()}\n"
                    f"Usado: {percentual:.0f}% (R$ {total:.2f} de R$ {lim.valor:.2f})\n\n"
                    f"💡 Você está perto do limite. Segure os gastos!"
                )
                self.send_telegram(chat_id, msg)
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

            # Alerta semanal (verificar se já enviou esta semana)
            if percentual < 10 and datetime.now().day == 1:
                msg = (
                    f"🏦 LEMBRETE DE RESERVA\n"
                    f"Meta: R$ {meta:.2f}\n"
                    f"Atual: R$ {atual:.2f} ({percentual:.1f}%)\n"
                    f"Faltante: R$ {meta - atual:.2f}\n\n"
                    f"📌 Sua reserva de emergência está baixa.\n"
                    f"Tente guardar pelo menos R$ {(meta - atual)/12:.2f} este mês."
                )
                self.send_telegram(chat_id, msg)
                return ["reserva_baixa"]

        return []

    def _alerta_divida(self, chat_id: str):
        from models.database import Divida

        dividas = self.db.query(Divida).all()
        total = sum(d.valor for d in dividas)

        if total > 0 and datetime.now().day in [5, 15, 25]:
            msg = (
                f"💳 CHECK-UP DE DÍVIDAS\n"
                f"Total pendente: R$ {total:.2f}\n"
                f"Próximo na lista: {dividas[0].nome.upper()} - R$ {dividas[0].valor:.2f}\n\n"
                f"🎯 Meta do mês: R$ {total/3:.2f}\n"
                f"Qualquer renda extra deve ir para cá primeiro!"
            )
            self.send_telegram(chat_id, msg)
            return ["divida_checkup"]

        return []
