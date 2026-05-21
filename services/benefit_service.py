from datetime import date, datetime


class BenefitCardService:
    def __init__(self, db_session):
        self.db = db_session

    def _card(self):
        from models.database import CartaoAlimentacao

        card = self.db.query(CartaoAlimentacao).filter(CartaoAlimentacao.ativo == True).first()
        if not card:
            card = CartaoAlimentacao(nome="cartao alimentacao", saldo_atual=0.0, recarga_mensal=0.0, dia_recarga=1)
            self.db.add(card)
            self.db.commit()
        return card

    def resumo(self, limite=8):
        from models.database import MovimentoAlimentacao

        card = self._card()
        movimentos = (
            self.db.query(MovimentoAlimentacao)
            .order_by(MovimentoAlimentacao.created_at.desc())
            .limit(limite)
            .all()
        )

        saldo = round(card.saldo_atual or 0, 2)
        recarga = round(card.recarga_mensal or 0, 2)
        percentual = round((saldo / recarga) * 100, 1) if recarga > 0 else None

        return {
            "ok": True,
            "cartao": {
                "id": card.id,
                "nome": card.nome,
                "saldo_atual": saldo,
                "recarga_mensal": recarga,
                "dia_recarga": card.dia_recarga or 1,
                "dias_ate_recarga": self._dias_ate_recarga(card.dia_recarga or 1),
                "percentual_recarga": percentual,
                "status": self._status(saldo, recarga),
                "sugestao": self._sugestao(saldo, recarga),
                "updated_at": card.updated_at.isoformat() if card.updated_at else "",
            },
            "movimentos": [self._movimento_json(m) for m in movimentos],
        }

    def configurar(self, data):
        card = self._card()

        if "nome" in data and str(data["nome"]).strip():
            card.nome = str(data["nome"]).strip()
        if "recarga_mensal" in data:
            card.recarga_mensal = max(float(data.get("recarga_mensal") or 0), 0)
        if "dia_recarga" in data:
            card.dia_recarga = min(max(int(data.get("dia_recarga") or 1), 1), 31)
        if "saldo_atual" in data:
            saldo_anterior = round(card.saldo_atual or 0, 2)
            novo_saldo = max(float(data.get("saldo_atual") or 0), 0)
            card.saldo_atual = round(novo_saldo, 2)
            if card.saldo_atual != saldo_anterior:
                self._registrar_movimento("ajuste", "Ajuste manual de saldo", novo_saldo, card.saldo_atual)

        card.updated_at = datetime.utcnow()
        self.db.commit()
        return self.resumo()

    def movimentar(self, tipo, valor, descricao=None):
        card = self._card()
        tipo = (tipo or "debito").strip().lower()
        valor = round(abs(float(valor or 0)), 2)
        if valor <= 0:
            return {"ok": False, "erro": "valor_invalido", "sugestao": "Informe um valor maior que zero."}

        descricao = (descricao or "").strip() or ("Recarga" if tipo == "credito" else "Uso no cartao alimentacao")
        saldo_atual = round(card.saldo_atual or 0, 2)

        if tipo == "debito":
            if valor > saldo_atual:
                return {
                    "ok": False,
                    "erro": "saldo_insuficiente",
                    "saldo_atual": saldo_atual,
                    "sugestao": "Esse gasto passa do saldo do cartao alimentacao. Use outro pagamento ou reduza a compra.",
                }
            card.saldo_atual = round(saldo_atual - valor, 2)
        elif tipo == "credito":
            card.saldo_atual = round(saldo_atual + valor, 2)
        elif tipo == "ajuste":
            card.saldo_atual = valor
        else:
            return {"ok": False, "erro": "tipo_invalido", "sugestao": "Use credito, debito ou ajuste."}

        card.updated_at = datetime.utcnow()
        self._registrar_movimento(tipo, descricao, valor, card.saldo_atual)
        self.db.commit()
        return self.resumo()

    def _registrar_movimento(self, tipo, descricao, valor, saldo_apos):
        from models.database import MovimentoAlimentacao

        self.db.add(MovimentoAlimentacao(
            tipo=tipo,
            descricao=descricao,
            valor=round(float(valor or 0), 2),
            saldo_apos=round(float(saldo_apos or 0), 2),
        ))

    def _movimento_json(self, mov):
        return {
            "id": mov.id,
            "tipo": mov.tipo,
            "descricao": mov.descricao,
            "valor": round(mov.valor or 0, 2),
            "saldo_apos": round(mov.saldo_apos or 0, 2),
            "created_at": mov.created_at.isoformat() if mov.created_at else "",
        }

    def _dias_ate_recarga(self, dia_recarga):
        hoje = date.today()
        dia = min(max(int(dia_recarga or 1), 1), 28)
        proxima = date(hoje.year, hoje.month, dia)
        if proxima < hoje:
            if hoje.month == 12:
                proxima = date(hoje.year + 1, 1, dia)
            else:
                proxima = date(hoje.year, hoje.month + 1, dia)
        return (proxima - hoje).days

    def _status(self, saldo, recarga):
        if recarga <= 0:
            return "configurar"
        percentual = (saldo / recarga) * 100
        if percentual < 15:
            return "critico"
        if percentual < 35:
            return "atencao"
        return "ok"

    def _sugestao(self, saldo, recarga):
        if recarga <= 0:
            return "Configure a recarga mensal para o app calcular se o saldo esta saudavel."
        percentual = (saldo / recarga) * 100
        if percentual < 15:
            return "Saldo baixo. Reserve o cartao para mercado e refeicoes essenciais ate a proxima recarga."
        if percentual < 35:
            return "Use com criterio. Priorize compras grandes planejadas e evite lanches por impulso."
        return "Saldo confortavel. Continue registrando cada uso para manter previsibilidade."
