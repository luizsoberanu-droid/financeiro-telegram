from datetime import datetime
import requests


DEFAULT_TICKERS = [
    "^BVSP",
    "^GSPC",
    "^IXIC",
    "USDBRL=X",
    "BOVA11.SA",
    "IVVB11.SA",
    "SMAL11.SA",
    "PETR4.SA",
    "VALE3.SA",
    "ITUB4.SA",
    "WEGE3.SA",
    "BBAS3.SA",
]


class MarketService:
    def snapshot(self, tickers=None):
        tickers = tickers or DEFAULT_TICKERS
        rows = []
        for ticker in tickers[:16]:
            rows.append(self._quote(ticker))

        ok_rows = [r for r in rows if r.get("ok")]
        return {
            "ok": bool(ok_rows),
            "fonte": "Yahoo Finance chart API",
            "observacao": "Dados de mercado podem atrasar e nao sao garantia de retorno.",
            "generated_at": datetime.utcnow().isoformat(),
            "ativos": rows,
        }

    def _quote(self, ticker):
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            r = requests.get(
                url,
                params={"range": "6mo", "interval": "1d"},
                headers={"User-Agent": "Mozilla/5.0 AurumCapitalBot/1.0"},
                timeout=12,
            )
            if not r.ok:
                return {"ok": False, "ticker": ticker, "erro": f"HTTP {r.status_code}"}

            result = (r.json().get("chart", {}).get("result") or [None])[0]
            if not result:
                return {"ok": False, "ticker": ticker, "erro": "sem dados"}

            meta = result.get("meta", {})
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [float(c) for c in closes if isinstance(c, (int, float)) and c > 0]
            if not closes:
                return {"ok": False, "ticker": ticker, "erro": "sem fechamento"}

            price = closes[-1]
            ret_1d = self._return(closes, 1)
            ret_30d = self._return(closes, 22)
            ret_6m = self._return(closes, min(126, len(closes) - 1))

            return {
                "ok": True,
                "ticker": ticker,
                "nome": meta.get("shortName") or meta.get("symbol") or ticker,
                "moeda": meta.get("currency", ""),
                "preco": round(price, 2),
                "retorno_1d_pct": ret_1d,
                "retorno_30d_pct": ret_30d,
                "retorno_6m_pct": ret_6m,
            }
        except Exception as e:
            return {"ok": False, "ticker": ticker, "erro": str(e)}

    def _return(self, closes, periods):
        if periods <= 0 or len(closes) <= periods:
            return None
        base = closes[-periods - 1]
        if base <= 0:
            return None
        return round(((closes[-1] / base) - 1) * 100, 2)
