import os
from datetime import datetime

from sqlalchemy import text


class PersistenceService:
    """Health view for long-term storage, backups and Render settings."""

    def __init__(self, db_session):
        self.db = db_session

    def status(self):
        from models.database import (
            Apontamento,
            Conversa,
            Desejo,
            Lancamento,
            PrecoDesejoHistorico,
            ResumoMensal,
            database_info,
        )
        from services.sheets_backup_service import SheetsBackupService

        banco = database_info()
        google = SheetsBackupService(self.db)
        historico = {
            "resumos_mensais": self._count(ResumoMensal),
            "lancamentos": self._count(Lancamento),
            "desejos": self._count(Desejo),
            "precos_desejos": self._count(PrecoDesejoHistorico),
            "conversas_ia": self._count(Conversa),
            "apontamentos": self._count(Apontamento),
        }

        ultimo_resumo = (
            self.db.query(ResumoMensal)
            .order_by(ResumoMensal.mes_ref.desc())
            .first()
        )

        banco_ok = self._check_database()
        google_configurado = google.enabled
        backup_por_mutacao = self._env_true("GOOGLE_SHEETS_BACKUP_EVERY_MUTATION", "false")
        restore_no_boot = self._env_true("GOOGLE_SHEETS_RESTORE_ON_START", "true")
        cron_interno = self._env_true("AURUM_ENABLE_INTERNAL_CRON", "false")
        telegram_automations = self._env_true("TELEGRAM_AUTOMATIONS_ENABLED", "false")

        acoes = []
        if not banco.get("is_persistent"):
            acoes.append("No Render, crie um Postgres e configure DATABASE_URL para manter o historico mesmo quando o app reiniciar.")
        if not google_configurado:
            acoes.append("Configure GOOGLE_SHEETS_ID e GOOGLE_SERVICE_ACCOUNT_JSON para ter um espelho externo dos dados.")
        if not historico["resumos_mensais"]:
            acoes.append("Atualize o historico mensal para a IA comparar o saldo final com meses anteriores.")
        if backup_por_mutacao:
            acoes.append("No Render com pouca memoria, prefira GOOGLE_SHEETS_BACKUP_EVERY_MUTATION=false e backup manual ou cron externo.")
        if cron_interno:
            acoes.append("Se houver erro de memoria no Render, mantenha AURUM_ENABLE_INTERNAL_CRON=false e use cron externo.")
        if not telegram_automations:
            acoes.append("Para receber check-ups e alertas automaticos, habilite TELEGRAM_AUTOMATIONS_ENABLED=true e chame os endpoints por cron externo.")

        nivel = "forte" if banco.get("is_persistent") else "atencao"
        if banco.get("is_persistent") and google_configurado:
            nivel = "blindado"
        elif not banco.get("is_persistent") and not google_configurado:
            nivel = "risco"

        return {
            "ok": banco_ok,
            "nivel": nivel,
            "checked_at": datetime.utcnow().isoformat(),
            "banco": banco,
            "google_sheets": {
                "configurado": google_configurado,
                "sheet_id_configurado": bool(os.getenv("GOOGLE_SHEETS_ID", "").strip()),
                "credencial_configurada": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()),
                "restore_no_boot": restore_no_boot,
                "backup_por_mutacao": backup_por_mutacao,
            },
            "render": {
                "cron_interno": cron_interno,
                "telegram_automations": telegram_automations,
                "web_concurrency": os.getenv("WEB_CONCURRENCY", "1"),
                "gunicorn_threads": os.getenv("GUNICORN_THREADS", "2"),
                "db_pool_size": os.getenv("DB_POOL_SIZE", "2"),
                "db_max_overflow": os.getenv("DB_MAX_OVERFLOW", "2"),
            },
            "historico": historico,
            "ultimo_resumo_mensal": self._serialize_resumo(ultimo_resumo),
            "acoes_recomendadas": acoes,
            "leitura": self._leitura(nivel),
        }

    def _check_database(self):
        try:
            self.db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def _count(self, model):
        try:
            return self.db.query(model).count()
        except Exception:
            return 0

    def _serialize_resumo(self, resumo):
        if not resumo:
            return None
        return {
            "mes_ref": resumo.mes_ref,
            "saldo_inicial": round(resumo.saldo_inicial or 0, 2),
            "saldo_final": round(resumo.saldo_final or 0, 2),
            "saldo_projetado": round(resumo.saldo_projetado or 0, 2),
            "updated_at": resumo.updated_at.isoformat() if resumo.updated_at else None,
        }

    def _leitura(self, nivel):
        if nivel == "blindado":
            return "Banco persistente e Google Sheets configurados. Este e o melhor desenho para a IA manter memoria financeira de longo prazo."
        if nivel == "forte":
            return "Banco persistente ativo. O historico principal esta protegido; Google Sheets ainda pode servir como backup extra."
        if nivel == "atencao":
            return "O app esta funcional, mas no Render o SQLite pode ser perdido em reinicios. Configure DATABASE_URL para ficar robusto."
        return "Persistencia fragil para uso vitalicio. Prioridade agora: DATABASE_URL persistente e backup externo."

    def _env_true(self, name, default="false"):
        return os.getenv(name, default).lower() in ["true", "1", "sim", "yes"]
