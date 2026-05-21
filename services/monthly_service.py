from datetime import datetime
from models.database import Config, ContaFixa, Lancamento, Parcela, Divida, ResumoMensal


def mes_atual():
    return datetime.now().strftime("%Y-%m")


class MonthlyService:
    def __init__(self, db_session):
        self.db = db_session

    def _mes_anterior(self, mes_ref):
        ano, mes = [int(x) for x in mes_ref.split("-")]
        mes -= 1
        if mes == 0:
            ano -= 1
            mes = 12
        return f"{ano:04d}-{mes:02d}"

    def _saldo_resumo(self, resumo):
        if not resumo:
            return None
        saldo_final = resumo.saldo_final
        if (saldo_final is None or saldo_final == 0) and (resumo.saldo_projetado or 0) != 0:
            saldo_final = resumo.saldo_projetado
        return round(saldo_final or 0, 2)

    def _saldo_inicial_mes(self, mes_ref, config):
        if config and config.saldo_conta_mes_ref == mes_ref:
            return round(config.saldo_conta_atual or 0, 2)

        mes_anterior = self._mes_anterior(mes_ref)
        resumo_anterior = (
            self.db.query(ResumoMensal)
            .filter(ResumoMensal.mes_ref == mes_anterior)
            .first()
        )
        saldo_anterior = self._saldo_resumo(resumo_anterior)
        if saldo_anterior is not None:
            return saldo_anterior

        return round((config.saldo_conta_atual if config else 0) or 0, 2)

    def calcular_mes(self, mes_ref=None):
        mes_ref = mes_ref or mes_atual()

        config = self.db.query(Config).first()
        if not config:
            return {
                "mes_ref": mes_ref,
                "saldo_inicial": 0,
                "receita_total": 0,
                "contas_pendentes": 0,
                "gastos_mes": 0,
                "parcelas_mes": 0,
                "movimento_mes": 0,
                "saldo_final": 0,
                "saldo_projetado": 0,
                "divida_bruta": 0,
                "divida_ajustada": 0,
                "reserva_atual": 0,
            }

        saldo_inicial = self._saldo_inicial_mes(mes_ref, config)
        receita_total = (config.receita_fixa or 0) + (config.receita_extra or 0)

        contas_pendentes = sum(
            c.valor for c in self.db.query(ContaFixa).filter(ContaFixa.pago == False).all()
        )
        gastos_mes = sum(l.valor for l in self.db.query(Lancamento).filter(Lancamento.mes_ref == mes_ref).all())
        parcelas_mes = sum(p.valor for p in self.db.query(Parcela).filter(Parcela.mes_ref == mes_ref).all())

        movimento_mes = receita_total - contas_pendentes - gastos_mes - parcelas_mes
        saldo_final = saldo_inicial + movimento_mes

        dividas = self.db.query(Divida).all()
        divida_bruta = sum(d.valor for d in dividas)
        divida_ajustada = max(divida_bruta - saldo_final, 0)

        return {
            "mes_ref": mes_ref,
            "saldo_inicial": round(saldo_inicial, 2),
            "receita_total": round(receita_total, 2),
            "contas_pendentes": round(contas_pendentes, 2),
            "gastos_mes": round(gastos_mes, 2),
            "parcelas_mes": round(parcelas_mes, 2),
            "movimento_mes": round(movimento_mes, 2),
            "saldo_final": round(saldo_final, 2),
            "saldo_projetado": round(saldo_final, 2),
            "divida_bruta": round(divida_bruta, 2),
            "divida_ajustada": round(divida_ajustada, 2),
            "reserva_atual": round(config.reserva_atual or 0, 2),
        }

    def salvar_resumo_mes(self, mes_ref=None):
        dados = self.calcular_mes(mes_ref)
        resumo = self.db.query(ResumoMensal).filter(ResumoMensal.mes_ref == dados["mes_ref"]).first()

        if not resumo:
            resumo = ResumoMensal(mes_ref=dados["mes_ref"])
            self.db.add(resumo)

        resumo.saldo_inicial = dados["saldo_inicial"]
        resumo.receita_total = dados["receita_total"]
        resumo.contas_pendentes = dados["contas_pendentes"]
        resumo.gastos_mes = dados["gastos_mes"]
        resumo.parcelas_mes = dados["parcelas_mes"]
        resumo.movimento_mes = dados["movimento_mes"]
        resumo.saldo_final = dados["saldo_final"]
        resumo.saldo_projetado = dados["saldo_projetado"]
        resumo.divida_bruta = dados["divida_bruta"]
        resumo.divida_ajustada = dados["divida_ajustada"]
        resumo.reserva_atual = dados["reserva_atual"]
        resumo.updated_at = datetime.utcnow()

        self.db.commit()
        return dados

    def historico(self, limite=12):
        self.salvar_resumo_mes()

        rows = (
            self.db.query(ResumoMensal)
            .order_by(ResumoMensal.mes_ref.desc())
            .limit(limite)
            .all()
        )

        historico = []
        for r in rows:
            saldo_final = self._saldo_resumo(r)
            movimento_mes = r.movimento_mes
            if (movimento_mes is None or movimento_mes == 0) and (r.saldo_projetado or 0) != 0:
                movimento_mes = (r.saldo_projetado or 0) - (r.saldo_inicial or 0)

            historico.append({
                "mes_ref": r.mes_ref,
                "saldo_inicial": round(r.saldo_inicial or 0, 2),
                "receita_total": round(r.receita_total or 0, 2),
                "contas_pendentes": round(r.contas_pendentes or 0, 2),
                "gastos_mes": round(r.gastos_mes or 0, 2),
                "parcelas_mes": round(r.parcelas_mes or 0, 2),
                "movimento_mes": round(movimento_mes or 0, 2),
                "saldo_final": round(saldo_final or 0, 2),
                "saldo_projetado": round(saldo_final or 0, 2),
                "divida_bruta": round(r.divida_bruta or 0, 2),
                "divida_ajustada": round(r.divida_ajustada or 0, 2),
                "reserva_atual": round(r.reserva_atual or 0, 2),
            })

        return historico
