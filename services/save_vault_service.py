from datetime import datetime


class SaveVaultService:
    """Portable JSON snapshot for long-term personal data ownership."""

    SNAPSHOT_VERSION = "aurum-capital-vitalicio-1"

    def __init__(self, db_session):
        self.db = db_session

    def models(self):
        from models.database import (
            Alerta,
            Apontamento,
            Cartao,
            CartaoAlimentacao,
            Config,
            ContaFixa,
            Conversa,
            Desejo,
            Divida,
            Lancamento,
            Limite,
            MovimentoAlimentacao,
            Parcela,
            PrecoDesejoHistorico,
            ResumoMensal,
        )

        return [
            ("config", Config),
            ("apontamentos", Apontamento),
            ("contas_fixas", ContaFixa),
            ("cartoes", Cartao),
            ("cartao_alimentacao", CartaoAlimentacao),
            ("movimentos_alimentacao", MovimentoAlimentacao),
            ("dividas", Divida),
            ("limites", Limite),
            ("lancamentos", Lancamento),
            ("parcelas", Parcela),
            ("resumo_mensal", ResumoMensal),
            ("desejos", Desejo),
            ("precos_desejos_historico", PrecoDesejoHistorico),
            ("conversas", Conversa),
            ("alertas", Alerta),
        ]

    def status(self):
        tables = {}
        total = 0
        for name, model in self.models():
            count = self.db.query(model).count()
            tables[name] = count
            total += count

        return {
            "ok": True,
            "snapshot_version": self.SNAPSHOT_VERSION,
            "total_registros": total,
            "tabelas": tables,
            "estrategia": [
                "Postgres persistente deve guardar o uso real no Render.",
                "SQLite fica como modo local/teste.",
                "Google Sheets funciona como espelho permanente.",
                "Snapshot JSON permite baixar uma copia portatil quando quiser.",
            ],
            "sugestao": "Use DATABASE_URL com Postgres no Render, salve no Google Sheets apos mudancas importantes e baixe um snapshot JSON pelo menos uma vez por mes.",
            "checked_at": datetime.utcnow().isoformat(),
        }

    def snapshot(self):
        data = {
            "app": "Aurum Capital",
            "snapshot_version": self.SNAPSHOT_VERSION,
            "generated_at": datetime.utcnow().isoformat(),
            "tables": {},
        }

        for name, model in self.models():
            columns = [c.name for c in model.__table__.columns]
            rows = []
            for obj in self.db.query(model).all():
                rows.append({col: self._serialize(getattr(obj, col)) for col in columns})
            data["tables"][name] = {"columns": columns, "rows": rows}

        return data

    def restore_snapshot(self, payload, replace=True):
        if not isinstance(payload, dict) or "tables" not in payload:
            return {"ok": False, "erro": "snapshot_invalido"}

        restored = {}
        table_payloads = payload.get("tables") or {}

        for name, model in self.models():
            if name not in table_payloads:
                continue

            if replace:
                self.db.query(model).delete()

            cols_by_name = {c.name: c for c in model.__table__.columns}
            rows = table_payloads[name].get("rows", []) if isinstance(table_payloads[name], dict) else []
            count = 0

            for row in rows:
                if not isinstance(row, dict):
                    continue
                parsed = {}
                for key, value in row.items():
                    if key not in cols_by_name:
                        continue
                    parsed[key] = self._parse(cols_by_name[key], value)
                if parsed:
                    self.db.add(model(**parsed))
                    count += 1

            restored[name] = count

        self.db.commit()
        return {"ok": True, "restored": restored, "restored_at": datetime.utcnow().isoformat()}

    def _serialize(self, value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _parse(self, column, value):
        from sqlalchemy import Boolean, DateTime, Float, Integer

        if value is None or value == "":
            return None
        ctype = column.type
        try:
            if isinstance(ctype, Integer):
                return int(float(value))
            if isinstance(ctype, Float):
                return float(value)
            if isinstance(ctype, Boolean):
                return str(value).lower() in ["true", "1", "sim", "yes"]
            if isinstance(ctype, DateTime):
                return datetime.fromisoformat(str(value))
        except Exception:
            return value
        return value
