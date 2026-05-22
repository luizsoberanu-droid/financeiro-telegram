from datetime import datetime, date
from io import BytesIO
import os

REPORTLAB_AVAILABLE = None


def _load_reportlab():
    global REPORTLAB_AVAILABLE, A4, getSampleStyleSheet, ParagraphStyle, cm
    global SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    global colors, TA_CENTER, TA_LEFT, TA_RIGHT

    if REPORTLAB_AVAILABLE is not None:
        return REPORTLAB_AVAILABLE

    try:
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib.styles import getSampleStyleSheet as _getSampleStyleSheet, ParagraphStyle as _ParagraphStyle
        from reportlab.lib.units import cm as _cm
        from reportlab.platypus import SimpleDocTemplate as _SimpleDocTemplate, Paragraph as _Paragraph, Spacer as _Spacer, Table as _Table, TableStyle as _TableStyle, PageBreak as _PageBreak
        from reportlab.lib import colors as _colors
        from reportlab.lib.enums import TA_CENTER as _TA_CENTER, TA_LEFT as _TA_LEFT, TA_RIGHT as _TA_RIGHT

        A4 = _A4
        getSampleStyleSheet = _getSampleStyleSheet
        ParagraphStyle = _ParagraphStyle
        cm = _cm
        SimpleDocTemplate = _SimpleDocTemplate
        Paragraph = _Paragraph
        Spacer = _Spacer
        Table = _Table
        TableStyle = _TableStyle
        PageBreak = _PageBreak
        colors = _colors
        TA_CENTER = _TA_CENTER
        TA_LEFT = _TA_LEFT
        TA_RIGHT = _TA_RIGHT
        REPORTLAB_AVAILABLE = True
    except ImportError:
        REPORTLAB_AVAILABLE = False
        print("reportlab nao instalado. PDF sera gerado em formato HTML.")
    return REPORTLAB_AVAILABLE

class PDFService:
    def __init__(self, db_session):
        self.db = db_session

    def gerar_relatorio_mensal(self, mes_ref=None):
        if not mes_ref:
            mes_ref = datetime.now().strftime("%Y-%m")

        from services.ai_service import FinancialTools
        from models.database import Config, Lancamento, Parcela, ContaFixa, Divida

        tools = FinancialTools(self.db)
        saldo = tools.get_saldo_atual()
        dividas = tools.get_analise_dividas()
        reserva = tools.get_reserva_status()
        plano = tools.get_plano_mensal()

        lancamentos = self.db.query(Lancamento).filter(Lancamento.mes_ref == mes_ref).order_by(Lancamento.data.desc()).all()
        parcelas = self.db.query(Parcela).filter(Parcela.mes_ref == mes_ref).all()
        contas = self.db.query(ContaFixa).all()

        if _load_reportlab():
            return self._gerar_pdf_reportlab(mes_ref, saldo, dividas, reserva, plano, lancamentos, parcelas, contas)
        else:
            return self._gerar_pdf_html(mes_ref, saldo, dividas, reserva, plano, lancamentos, parcelas, contas)

    def _gerar_pdf_reportlab(self, mes_ref, saldo, dividas, reserva, plano, lancamentos, parcelas, contas):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24,
            textColor=colors.HexColor('#1a1a2e'), spaceAfter=30, alignment=TA_CENTER)
        heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14,
            textColor=colors.HexColor('#00d4ff'), spaceAfter=12, spaceBefore=12)
        normal_style = styles['Normal']
        normal_style.fontSize = 10

        story = []
        mes_nome = self._mes_nome(mes_ref)
        story.append(Paragraph("RELATORIO FINANCEIRO", title_style))
        story.append(Paragraph("<b>" + mes_nome + "</b>",
            ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=12, alignment=TA_CENTER, textColor=colors.grey)))
        story.append(Spacer(1, 20))

        story.append(Paragraph("RESUMO EXECUTIVO", heading_style))
        resumo_data = [
            ["Saldo Inicial", "R$ " + str(round(saldo.get('saldo_inicial', 0), 2))],
            ["Receita Total", "R$ " + str(round(saldo['receita_total'], 2))],
            ["Contas Fixas", "R$ " + str(round(saldo['contas_pendentes'], 2))],
            ["Gastos Variaveis", "R$ " + str(round(saldo['gastos_mes'], 2))],
            ["Parcelas", "R$ " + str(round(saldo['parcelas_mes'], 2))],
            ["Movimento do Mes", "R$ " + str(round(saldo.get('movimento_mes', 0), 2))],
            ["Saldo Final", "R$ " + str(round(saldo.get('saldo_final', saldo['saldo_projetado']), 2))],
            ["Divida Total", "R$ " + str(round(dividas['total_divida'], 2))],
            ["Reserva", "R$ " + str(round(reserva['atual'], 2)) + " / R$ " + str(round(reserva['meta'], 2))],
        ]
        resumo_table = Table(resumo_data, colWidths=[8*cm, 8*cm])
        resumo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(resumo_table)
        story.append(Spacer(1, 20))

        story.append(Paragraph("CONTAS FIXAS", heading_style))
        contas_data = [["Conta", "Valor", "Vencimento", "Status"]]
        for c in contas:
            contas_data.append([c.nome, "R$ " + str(round(c.valor, 2)), "Dia " + str(c.vencimento), "Paga" if c.pago else "Aberta"])
        contas_table = Table(contas_data, colWidths=[6*cm, 4*cm, 3*cm, 3*cm])
        contas_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00d4ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        story.append(contas_table)
        story.append(Spacer(1, 20))

        if lancamentos:
            story.append(Paragraph("LANCAMENTOS DO MES", heading_style))
            lanc_data = [["Data", "Descricao", "Categoria", "Valor", "Pagamento"]]
            for l in lancamentos:
                lanc_data.append([l.data.strftime("%d/%m"), l.descricao[:25], l.categoria,
                    "R$ " + str(round(l.valor, 2)), l.forma_pagamento])
            lanc_table = Table(lanc_data, colWidths=[2.5*cm, 6*cm, 3*cm, 3*cm, 3*cm])
            lanc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7b2cbf')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            story.append(lanc_table)
            story.append(Spacer(1, 20))

        if dividas['total_divida'] > 0:
            story.append(Paragraph("DIVIDAS", heading_style))
            div_data = [["Credor", "Valor", "Prioridade"]]
            for d in dividas['detalhes']:
                div_data.append([d['nome'], "R$ " + str(round(d['valor'], 2)), str(d['prioridade'])])
            div_table = Table(div_data, colWidths=[8*cm, 4*cm, 4*cm])
            div_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ff4757')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            story.append(div_table)
            story.append(Spacer(1, 20))

        story.append(Paragraph("RECOMENDACOES DA IA", heading_style))
        for acao in plano['acoes_recomendadas']:
            story.append(Paragraph("- " + acao, normal_style))

        story.append(Spacer(1, 30))
        story.append(Paragraph(
            "<i>Relatorio gerado por Aurum Capital em " + datetime.now().strftime('%d/%m/%Y %H:%M') + "</i>",
            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
        ))

        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    def _gerar_pdf_html(self, mes_ref, saldo, dividas, reserva, plano, lancamentos, parcelas, contas):
        mes_nome = self._mes_nome(mes_ref)
        saldo_final = saldo.get('saldo_final', saldo['saldo_projetado'])
        saldo_class = "positive" if saldo_final >= 0 else "negative"

        linhas_contas = ""
        for c in contas:
            status = "Paga" if c.pago else "Aberta"
            linhas_contas += "<tr><td>" + c.nome + "</td><td>R$ " + str(round(c.valor, 2)) + "</td><td>Dia " + str(c.vencimento) + "</td><td>" + status + "</td></tr>"

        linhas_lancamentos = ""
        for l in lancamentos:
            linhas_lancamentos += "<tr><td>" + l.data.strftime('%d/%m') + "</td><td>" + l.descricao + "</td><td>" + l.categoria + "</td><td>R$ " + str(round(l.valor, 2)) + "</td></tr>"

        secao_lancamentos = ""
        if lancamentos:
            secao_lancamentos = "<h2>Lancamentos do Mes</h2><table><tr><th>Data</th><th>Descricao</th><th>Categoria</th><th>Valor</th></tr>" + linhas_lancamentos + "</table>"

        linhas_dividas = ""
        secao_dividas = ""
        if dividas['total_divida'] > 0:
            for d in dividas['detalhes']:
                linhas_dividas += "<tr><td>" + d['nome'] + "</td><td>R$ " + str(round(d['valor'], 2)) + "</td><td>" + str(d['prioridade']) + "</td></tr>"
            secao_dividas = "<h2>Dividas</h2><table><tr><th>Credor</th><th>Valor</th><th>Prioridade</th></tr>" + linhas_dividas + "</table>"

        itens_rec = ""
        for acao in plano['acoes_recomendadas']:
            itens_rec += "<li>" + acao + "</li>"

        html = (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Relatorio " + mes_nome + "</title>"
            "<style>"
            "body{font-family:Arial,sans-serif;margin:40px;color:#333}"
            "h1{color:#1a1a2e;text-align:center}"
            "h2{color:#00d4ff;border-bottom:2px solid #00d4ff;padding-bottom:5px;margin-top:30px}"
            "table{width:100%;border-collapse:collapse;margin:15px 0}"
            "th{background:#00d4ff;color:white;padding:10px;text-align:left}"
            "td{padding:8px 10px;border-bottom:1px solid #ddd}"
            "tr:nth-child(even){background:#f8f9fa}"
            ".resumo{background:#f8f9fa;padding:20px;border-radius:10px;margin:20px 0}"
            ".resumo-item{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #ddd}"
            ".positive{color:#00c853}.negative{color:#ff4757}"
            ".footer{text-align:center;color:#888;font-size:.85em;margin-top:40px}"
            "</style></head><body>"
            "<h1>RELATORIO FINANCEIRO</h1>"
            "<h3 style='text-align:center;color:#888'>" + mes_nome + "</h3>"
            "<h2>Resumo Executivo</h2><div class='resumo'>"
            "<div class='resumo-item'><span>Saldo Inicial</span><span>R$ " + str(round(saldo.get('saldo_inicial', 0), 2)) + "</span></div>"
            "<div class='resumo-item'><span>Receita Total</span><span><b>R$ " + str(round(saldo['receita_total'], 2)) + "</b></span></div>"
            "<div class='resumo-item'><span>Contas Fixas</span><span>R$ " + str(round(saldo['contas_pendentes'], 2)) + "</span></div>"
            "<div class='resumo-item'><span>Gastos Variaveis</span><span>R$ " + str(round(saldo['gastos_mes'], 2)) + "</span></div>"
            "<div class='resumo-item'><span>Parcelas</span><span>R$ " + str(round(saldo['parcelas_mes'], 2)) + "</span></div>"
            "<div class='resumo-item'><span>Movimento do Mes</span><span>R$ " + str(round(saldo.get('movimento_mes', 0), 2)) + "</span></div>"
            "<div class='resumo-item'><span><b>Saldo Final</b></span><span class='" + saldo_class + "'><b>R$ " + str(round(saldo_final, 2)) + "</b></span></div>"
            "<div class='resumo-item'><span>Divida Total</span><span class='negative'>R$ " + str(round(dividas['total_divida'], 2)) + "</span></div>"
            "<div class='resumo-item'><span>Reserva</span><span>R$ " + str(round(reserva['atual'], 2)) + " / R$ " + str(round(reserva['meta'], 2)) + " (" + str(round(reserva['percentual'], 1)) + "%)</span></div>"
            "</div>"
            "<h2>Contas Fixas</h2><table><tr><th>Conta</th><th>Valor</th><th>Vencimento</th><th>Status</th></tr>"
            + linhas_contas + "</table>"
            + secao_lancamentos
            + secao_dividas
            + "<h2>Recomendacoes da IA</h2><ul>" + itens_rec + "</ul>"
            "<div class='footer'><p>Relatorio gerado por Aurum Capital</p><p>" + datetime.now().strftime('%d/%m/%Y %H:%M') + "</p></div>"
            "</body></html>"
        )

        return html.encode('utf-8')

    def _mes_nome(self, mes_ref):
        y, m = mes_ref.split("-")
        nomes = ["Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        return nomes[int(m)-1] + " de " + y
