import json
from datetime import datetime


class AutosaveService:
    def __init__(self, db_session):
        self.db = db_session

    def registrar_request(self, request, response):
        if response.status_code >= 400:
            return None

        if request.path in self._ignored_paths():
            return None

        body = request.get_json(silent=True)
        entidade = self._entidade(request.path)
        acao = self._acao(request.method)
        resumo = self._resumo(entidade, acao, body, request.path)

        return self.registrar(
            origem="telegram" if request.path.startswith("/webhooks/") else "painel",
            metodo=request.method,
            caminho=request.path,
            entidade=entidade,
            acao=acao,
            resumo=resumo,
            payload=body,
            status_code=response.status_code,
        )

    def registrar(self, origem, metodo, caminho, entidade, acao, resumo, payload=None, status_code=200):
        from models.database import Apontamento

        apontamento = Apontamento(
            origem=origem,
            metodo=metodo,
            caminho=caminho,
            entidade=entidade,
            acao=acao,
            resumo=resumo[:500],
            payload=self._payload(payload),
            status_code=int(status_code or 200),
            created_at=datetime.utcnow(),
        )
        self.db.add(apontamento)
        self.db.commit()
        return apontamento

    def recentes(self, limite=20):
        from models.database import Apontamento

        rows = (
            self.db.query(Apontamento)
            .order_by(Apontamento.created_at.desc())
            .limit(limite)
            .all()
        )

        return [{
            "id": a.id,
            "origem": a.origem,
            "metodo": a.metodo,
            "caminho": a.caminho,
            "entidade": a.entidade,
            "acao": a.acao,
            "resumo": a.resumo,
            "status_code": a.status_code,
            "created_at": a.created_at.isoformat() if a.created_at else "",
        } for a in rows]

    def _payload(self, payload):
        if payload is None:
            return None
        try:
            text = json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            text = str(payload)
        return text[:4000]

    def _ignored_paths(self):
        return {
            "/api/ping",
            "/api/backup/google_sheets",
            "/api/restore/google_sheets",
            "/api/salvamento/google_sheets",
            "/api/salvamento/restaurar_google_sheets",
            "/api/salvamento/restaurar_snapshot",
            "/api/cartoes/recalcular_limites",
        }

    def _acao(self, method):
        if method == "POST":
            return "criar"
        if method == "PUT":
            return "atualizar"
        if method == "DELETE":
            return "excluir"
        return "alteracao"

    def _entidade(self, path):
        mapping = {
            "/api/lancar": "lancamento",
            "/api/parcelar": "parcela",
            "/api/add_conta_fixa": "conta",
            "/api/marcar_pago": "pagamento",
            "/api/add_cartao": "cartao",
            "/api/alimentacao": "cartao_alimentacao",
            "/api/config": "configuracao",
            "/api/limites": "limite",
            "/api/add_extra": "renda_extra",
            "/api/divida": "divida",
            "/api/desejo": "desejo",
            "/api/historico_mensal": "historico_mensal",
            "/api/alertas": "alerta",
            "/api/relatorio": "relatorio",
            "/webhooks/telegram": "telegram",
        }
        for prefix, entidade in mapping.items():
            if path.startswith(prefix):
                return entidade
        if path.startswith("/api/conta/"):
            return "conta"
        if path.startswith("/api/cartao/"):
            return "cartao"
        if path.startswith("/api/divida/"):
            return "divida"
        if path.startswith("/api/desejo/"):
            return "desejo"
        return "geral"

    def _resumo(self, entidade, acao, body, path):
        if isinstance(body, dict):
            nome = body.get("nome") or body.get("descricao") or body.get("tipo") or entidade
            valor = body.get("valor")
            if valor not in [None, ""]:
                return f"{acao} {entidade}: {nome} - R$ {valor}"
            return f"{acao} {entidade}: {nome}"
        return f"{acao} {entidade} em {path}"
