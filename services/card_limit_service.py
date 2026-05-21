from datetime import datetime


class CardLimitService:
    def __init__(self, db_session):
        self.db = db_session

    def calcular_limite_total_ideal(self):
        from models.database import Config, Divida

        config = self.db.query(Config).first()
        renda = ((config.receita_fixa or 0) + (config.receita_extra or 0)) if config else 0
        divida_total = sum(d.valor for d in self.db.query(Divida).all())

        if renda <= 0:
            return 0

        if divida_total > 0:
            percentual = 0.05
        elif config and (config.reserva_atual or 0) < (config.meta_reserva or 0):
            percentual = 0.08
        else:
            percentual = 0.12

        return round(renda * percentual, 2)

    def atualizar_limites_cartoes(self):
        from models.database import Cartao

        cartoes = self.db.query(Cartao).all()
        if not cartoes:
            return []

        total_ideal = self.calcular_limite_total_ideal()
        pesos = [max(c.limite_real or 0, 1) for c in cartoes]
        peso_total = sum(pesos) or len(cartoes)

        for c, peso in zip(cartoes, pesos):
            ideal = round(total_ideal * (peso / peso_total), 2)
            if (c.limite_real or 0) > 0:
                ideal = min(ideal, c.limite_real)
            c.limite_ideal = ideal

        self.db.commit()
        return self._cartoes_rows(cartoes)

    def atualizar_limite_real(self, nome_cartao, limite_real):
        from models.database import Cartao

        cartao = self.db.query(Cartao).filter(Cartao.nome.ilike(str(nome_cartao).strip())).first()
        if not cartao:
            return {"ok": False, "erro": "cartao_nao_encontrado"}

        cartao.limite_real = max(float(limite_real or 0), 0)
        self.db.commit()
        self.atualizar_limites_cartoes()
        return {"ok": True, "cartao": self._cartao_row(cartao)}

    def resumo_limites(self):
        from models.database import Cartao

        cartoes = self.db.query(Cartao).all()
        if not cartoes:
            return {
                "ok": True,
                "limite_total_real": 0,
                "limite_total_seguro_mes": 0,
                "uso_total_mes": 0,
                "disponivel_seguro_mes": 0,
                "cartoes": [],
                "leitura": "Nenhum cartao cadastrado.",
            }

        self.atualizar_limites_cartoes()
        cartoes = self.db.query(Cartao).all()
        rows = self._cartoes_rows(cartoes)
        limite_total_real = round(sum(r["limite_real"] for r in rows), 2)
        limite_total_seguro = round(sum(r["limite_ideal"] for r in rows), 2)
        uso_total = round(sum(r["uso_mes"] for r in rows), 2)
        disponivel_seguro = round(max(limite_total_seguro - uso_total, 0), 2)
        disponivel_real = round(max(limite_total_real - uso_total, 0), 2) if limite_total_real > 0 else 0

        if limite_total_real <= 0:
            leitura = "Informe o limite real dos cartoes para eu comparar banco x limite seguro."
        elif uso_total > limite_total_seguro:
            leitura = "Uso do cartao acima do limite seguro do mes. Congelar novas compras."
        else:
            leitura = "Cartao sob controle se novas compras respeitarem o limite seguro mensal."

        return {
            "ok": True,
            "limite_total_real": limite_total_real,
            "limite_total_seguro_mes": limite_total_seguro,
            "uso_total_mes": uso_total,
            "disponivel_seguro_mes": disponivel_seguro,
            "disponivel_real": disponivel_real,
            "cartoes": rows,
            "leitura": leitura,
        }

    def _uso_cartao_mes(self, nome_cartao):
        from models.database import Lancamento, Parcela

        mes_ref = datetime.now().strftime("%Y-%m")
        lancamentos = sum(l.valor for l in self.db.query(Lancamento).filter(
            Lancamento.forma_pagamento == "cartao",
            Lancamento.cartao == nome_cartao,
            Lancamento.mes_ref == mes_ref,
        ).all())
        parcelas = sum(p.valor for p in self.db.query(Parcela).filter(
            Parcela.cartao == nome_cartao,
            Parcela.mes_ref == mes_ref,
        ).all())
        return round((lancamentos or 0) + (parcelas or 0), 2)

    def _cartoes_rows(self, cartoes):
        return [self._cartao_row(c) for c in cartoes]

    def _cartao_row(self, c):
        uso_mes = self._uso_cartao_mes(c.nome)
        limite_real = round(c.limite_real or 0, 2)
        limite_ideal = round(c.limite_ideal or 0, 2)
        return {
            "id": c.id,
            "nome": c.nome,
            "vencimento": c.vencimento,
            "melhor_dia_compra": c.melhor_dia_compra,
            "limite_real": limite_real,
            "limite_ideal": limite_ideal,
            "uso_mes": uso_mes,
            "disponivel_real": round(max(limite_real - uso_mes, 0), 2) if limite_real > 0 else 0,
            "disponivel_seguro_mes": round(max(limite_ideal - uso_mes, 0), 2),
            "pago": bool(c.pago),
        }
