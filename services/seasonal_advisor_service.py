from datetime import date, datetime
import os
import requests


class SeasonalAdvisorService:
    def __init__(self, db_session):
        self.db = db_session

    def _estacao_brasil(self, hoje=None):
        hoje = hoje or date.today()
        ano = hoje.year
        estacoes = [
            ("verao", date(ano, 12, 21), date(ano + 1, 3, 19)),
            ("outono", date(ano, 3, 20), date(ano, 6, 20)),
            ("inverno", date(ano, 6, 21), date(ano, 9, 22)),
            ("primavera", date(ano, 9, 23), date(ano, 12, 20)),
        ]

        for nome, inicio, fim in estacoes:
            if inicio <= hoje <= fim:
                return nome, inicio, fim

        return "verao", date(ano - 1, 12, 21), date(ano, 3, 19)

    def _proxima_estacao(self, hoje=None):
        hoje = hoje or date.today()
        ano = hoje.year
        proximas = [
            ("outono", date(ano, 3, 20)),
            ("inverno", date(ano, 6, 21)),
            ("primavera", date(ano, 9, 23)),
            ("verao", date(ano, 12, 21)),
            ("outono", date(ano + 1, 3, 20)),
        ]
        for nome, inicio in proximas:
            if inicio > hoje:
                return nome, inicio, (inicio - hoje).days
        return "outono", date(ano + 1, 3, 20), (date(ano + 1, 3, 20) - hoje).days

    def _clima_atual(self):
        try:
            lat = float(os.getenv("AURUM_WEATHER_LAT", "-23.5505"))
            lon = float(os.getenv("AURUM_WEATHER_LON", "-46.6333"))
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,precipitation,weather_code",
                "daily": "temperature_2m_min,temperature_2m_max",
                "forecast_days": 7,
                "timezone": os.getenv("AURUM_WEATHER_TZ", "America/Sao_Paulo"),
            }
            try:
                r = requests.get(url, params=params, timeout=12)
            except requests.exceptions.SSLError:
                requests.packages.urllib3.disable_warnings()
                r = requests.get(url, params=params, timeout=12, verify=False)
            if not r.ok:
                return {"ok": False, "erro": f"Open-Meteo HTTP {r.status_code}"}
            data = r.json()
            current = data.get("current", {})
            daily = data.get("daily", {})
            mins = daily.get("temperature_2m_min", []) or []
            maxs = daily.get("temperature_2m_max", []) or []
            return {
                "ok": True,
                "temperatura": current.get("temperature_2m"),
                "chuva": current.get("precipitation"),
                "min_7d": min(mins) if mins else None,
                "max_7d": max(maxs) if maxs else None,
                "fonte": "Open-Meteo",
            }
        except Exception as e:
            return {"ok": False, "erro": str(e)}

    def _tem_item(self, termos):
        from models.database import Desejo

        desejos = self.db.query(Desejo).filter(Desejo.comprado == False).all()
        nomes = " ".join([(d.nome or "").lower() for d in desejos])
        return any(t in nomes for t in termos)

    def mensagem_sazonal(self):
        estacao, _, fim = self._estacao_brasil()
        proxima, inicio_proxima, dias = self._proxima_estacao()
        clima = self._clima_atual()

        sugestoes = []
        pergunta = None
        if proxima == "inverno" or estacao == "outono":
            termos = ["blusa", "moletom", "jaqueta", "casaco", "cobertor", "calca", "meia"]
            if not self._tem_item(termos):
                sugestoes = ["blusa de frio", "meias", "calca confortável", "cobertor"]
                pergunta = "Esta chegando o inverno. Voce tem roupas de frio em bom estado?"
        elif proxima == "verao" or estacao == "primavera":
            termos = ["bermuda", "camiseta", "regata", "ventilador", "protetor solar", "chinelo"]
            if not self._tem_item(termos):
                sugestoes = ["camisetas leves", "bermuda", "protetor solar", "ventilador"]
                pergunta = "Esta chegando o verao. Voce tem roupas leves e itens de calor?"

        if not pergunta:
            pergunta = "Revisei a estacao e sua lista de desejos. Nao vi urgencia sazonal clara agora."

        linhas = [
            "Check-up sazonal do Aurum Capital",
            "",
            f"Estacao atual: {estacao}. Proxima: {proxima} em {dias} dia(s), a partir de {inicio_proxima.strftime('%d/%m')}.",
        ]
        if clima.get("ok"):
            linhas.append(
                f"Clima consultado em {clima['fonte']}: agora {clima.get('temperatura')} C, "
                f"minima 7d {clima.get('min_7d')} C, maxima 7d {clima.get('max_7d')} C."
            )
        else:
            linhas.append("Nao consegui consultar o clima agora; usei a estacao do ano como referencia.")

        linhas.append("")
        linhas.append(pergunta)
        if sugestoes:
            linhas.append("Posso adicionar estes itens na lista de desejos com media real de preco na internet:")
            for item in sugestoes:
                linhas.append(f"- {item}")
        linhas.append("")
        linhas.append("Antes de comprar, eu confiro saldo final, dividas, fatura e reserva.")

        return {
            "ok": True,
            "estacao": estacao,
            "proxima_estacao": proxima,
            "dias_para_proxima": dias,
            "clima": clima,
            "sugestoes": sugestoes,
            "mensagem": "\n".join(linhas),
            "checked_at": datetime.utcnow().isoformat(),
        }
