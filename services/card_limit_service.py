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

        # Regra conservadora:
        # - com dívida: 5% da renda
        # - em reserva: 8% da renda
        # - crescimento: 12% da renda
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
        por_cartao = round(total_ideal / len(cartoes), 2)

        for c in cartoes:
            c.limite_ideal = por_cartao

        self.db.commit()

        return [{
            "id": c.id,
            "nome": c.nome,
            "limite_ideal": round(c.limite_ideal or 0, 2)
        } for c in cartoes]
