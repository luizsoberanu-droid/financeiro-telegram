from datetime import datetime, date, timedelta
import calendar

class FinanceService:
    def __init__(self, db_session):
        self.db = db_session

    def add_lancamento(self, descricao: str, valor: float, forma_pagamento: str = "dinheiro", 
                       cartao: str = None, categoria: str = None):
        from models.database import Lancamento, Cartao

        dt = datetime.now()
        mes_ref = dt.strftime("%Y-%m")

        if not categoria:
            categoria = self._infer_categoria(descricao)

        fatura_mes_ref = None
        fatura_vencimento = None
        if forma_pagamento == "cartao" and cartao:
            cart = self.db.query(Cartao).filter(Cartao.nome.ilike(cartao)).first()
            if cart:
                fatura_info = self._calcular_fatura(cart, dt.date())
                fatura_mes_ref = fatura_info["mes_ref"]
                fatura_vencimento = fatura_info["vencimento"]
                mes_ref = fatura_mes_ref

        lanc = Lancamento(
            data=dt, mes_ref=mes_ref, descricao=descricao,
            categoria=categoria, valor=round(float(valor), 2),
            forma_pagamento=forma_pagamento, cartao=cartao,
            fatura_mes_ref=fatura_mes_ref, fatura_vencimento=fatura_vencimento
        )
        self.db.add(lanc)
        self.db.commit()
        return lanc

    def add_parcelado(self, descricao: str, valor_parcela: float, total_parcelas: int, 
                      cartao: str, data_compra: date = None):
        from models.database import Parcela, Cartao

        dt = data_compra or date.today()
        cart = self.db.query(Cartao).filter(Cartao.nome.ilike(cartao)).first()
        if not cart:
            return None

        fatura_info = self._calcular_fatura(cart, dt)
        ano, mes = fatura_info["ano"], fatura_info["mes"]

        parcelas_criadas = []
        for i in range(total_parcelas):
            m = mes + i
            a = ano
            while m > 12:
                m -= 12
                a += 1
            p = Parcela(
                descricao=descricao, cartao=cartao,
                valor=round(float(valor_parcela), 2),
                parcela_atual=i + 1, total_parcelas=total_parcelas,
                mes_ref=f"{a:04d}-{m:02d}", vencimento=cart.vencimento
            )
            self.db.add(p)
            parcelas_criadas.append(p)

        self.db.commit()
        return parcelas_criadas

    def aplicar_extra(self, valor: float):
        from models.database import Config, Divida

        config = self.db.query(Config).first()
        config.receita_extra = (config.receita_extra or 0) + valor

        restante = valor
        abatimentos = []
        dividas = self.db.query(Divida).order_by(Divida.ordem_prioridade).all()

        for div in dividas:
            if div.valor <= 0:
                continue
            abatido = min(div.valor, restante)
            div.valor -= abatido
            restante -= abatido
            abatimentos.append({
                "nome": div.nome,
                "abatido": round(abatido, 2),
                "restante": round(div.valor, 2)
            })
            if restante <= 0:
                break

        self.db.commit()
        return abatimentos, round(restante, 2)

    def _infer_categoria(self, descricao: str) -> str:
        d = (descricao or "").strip().lower()
        categorias = {
            "lazer": ["lanche", "passeio", "cinema", "sorvete", "pizza", "hamburguer", 
                      "hambúrguer", "açai", "acai", "bar", "churrasco", "role"],
            "combustivel": ["gasolina", "etanol", "combustivel", "combustível", "posto"],
            "extras": ["mercado", "farmacia", "farmácia", "remedio", "remédio", 
                       "compra", "pix", "uber", "ifood", "delivery"],
            "moradia": ["aluguel", "condominio", "condomínio", "iptu", "agua", "água"],
            "educacao": ["faculdade", "curso", "livro", "material escolar", "aula"],
            "saude": ["medico", "médico", "dentista", "exame", "consulta"],
            "transporte": ["onibus", "ônibus", "metro", "metrô", "uber", "99", "taxi"]
        }
        for cat, palavras in categorias.items():
            if any(p in d for p in palavras):
                return cat
        return "extras"

    def _calcular_fatura(self, cartao, data_compra: date):
        melhor_dia = self._prev_business_day(data_compra.year, data_compra.month, cartao.melhor_dia_compra)
        if data_compra <= melhor_dia:
            ano, mes = data_compra.year, data_compra.month
        else:
            if data_compra.month == 12:
                ano, mes = data_compra.year + 1, 1
            else:
                ano, mes = data_compra.year, data_compra.month + 1
        return {
            "ano": ano, "mes": mes,
            "mes_ref": f"{ano:04d}-{mes:02d}",
            "vencimento": cartao.vencimento,
            "melhor_dia": melhor_dia.isoformat()
        }

    def _prev_business_day(self, year, month, day):
        last_day = calendar.monthrange(year, month)[1]
        d = date(year, month, min(day, last_day))
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d
