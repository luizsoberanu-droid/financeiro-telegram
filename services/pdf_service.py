from datetime import datetime, date
from io import BytesIO
import os

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️  reportlab não instalado. PDF será gerado em formato HTML.")

class PDFService:
    def __init__(self, db_session):
        self.db = db_session

    def gerar_relatorio_mensal(self, mes_ref=None):
        """Gera relatório mensal em PDF"""
        if not mes_ref:
            mes_ref = datetime.now().strftime("%Y-%m")

        from services.ai_service import FinancialTools
        from models.database import Config, Lancamento, Parcela, ContaFixa, Divida

        tools = FinancialTools(self.db)
        saldo = tools.get_saldo_atual()
        dividas = tools.get_analise_dividas()
        reserva = tools.get_reserva_status()
        plano = tools.get_plano_mensal()

        # Buscar dados do mês
        lancamentos = self.db.query(Lancamento).filter(Lancamento.mes_ref == mes_ref).order_by(Lancamento.data.desc()).all()
        parcelas = self.db.query(Parcela).filter(Parcela.mes_ref == mes_ref).all()
        contas = self.db.query(ContaFixa).all()

        if REPORTLAB_AVAILABLE:
            return self._gerar_pdf_reportlab(mes_ref, saldo, dividas, reserva, plano, lancamentos, parcelas, contas)
        else:
            return self._gerar_pdf_html(mes_ref, saldo, dividas, reserva, plano, lancamentos, parcelas, contas)

    def _gerar_pdf_reportlab(self, mes_ref, saldo, dividas, reserva, plano, lancamentos, parcelas, contas):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )

        styles = getSampleStyleSheet()

        # Estilos customizados
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a2e'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#00d4ff'),
            spaceAfter=12,
            spaceBefore=12
        )

        normal_style = styles['Normal']
        normal_style.fontSize = 10

        # Construir conteúdo
        story = []

        # Título
        mes_nome = self._mes_nome(mes_ref)
        story.append(Paragraph(f"📊 RELATÓRIO FINANCEIRO", title_style))
        story.append(Paragraph(f"<b>{mes_nome}</b>", ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=12, alignment=TA_CENTER, textColor=colors.grey)))
        story.append(Spacer(1, 20))

        # Resumo Executivo
        story.append(Paragraph("📈 RESUMO EXECUTIVO", heading_style))

        resumo_data = [
            ["Receita Total", f"R$ {saldo['receita_total']:.2f}"],
            ["Contas Fixas", f"R$ {saldo['contas_pendentes']:.2f}"],
            ["Gastos Variáveis", f"R$ {saldo['gastos_mes']:.2f}"],
            ["Parcelas", f"R$ {saldo['parcelas_mes']:.2f}"],
            ["Saldo Projetado", f"R$ {saldo['saldo_projetado']:.2f}"],
            ["Dívida Total", f"R$ {dividas['total_divida']:.2f}"],
            ["Reserva", f"R$ {reserva['atual']:.2f} / R$ {reserva['meta']:.2f} ({reserva['percentual']:.1f}%)"],
        ]

        resumo_table = Table(resumo_data, colWidths=[8*cm, 8*cm])
        resumo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(resumo_table)
        story.append(Spacer(1, 20))

        # Contas Fixas
        story.append(Paragraph("📋 CONTAS FIXAS", heading_style))
        contas_data = [["Conta", "Valor", "Vencimento", "Status"]]
        for c in contas:
            contas_data.append([c.nome, f"R$ {c.valor:.2f}", f"Dia {c.vencimento}", "✅ Paga" if c.pago else "⏳ Aberta"])

        contas_table = Table(contas_data, colWidths=[6*cm, 4*cm, 3*cm, 3*cm])
        contas_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00d4ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        story.append(contas_table)
        story.append(Spacer(1, 20))

        # Lançamentos
        if lancamentos:
            story.append(Paragraph("💸 LANÇAMENTOS DO MÊS", heading_style))
            lanc_data = [["Data", "Descrição", "Categoria", "Valor", "Pagamento"]]
            for l in lancamentos:
                lanc_data.append([
                    l.data.strftime("%d/%m"),
                    l.descricao[:25],
                    l.categoria,
                    f"R$ {l.valor:.2f}",
                    l.forma_pagamento
                ])

            lanc_table = Table(lanc_data, colWidths=[2.5*cm, 6*cm, 3*cm, 3*cm, 3*cm])
            lanc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7b2cbf')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('TOPPADDING', (0, 1), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(lanc_table)
            story.append(Spacer(1, 20))

        # Dívidas
        if dividas['total_divida'] > 0:
            story.append(Paragraph("💳 DÍVIDAS", heading_style))
            div_data = [["Credor", "Valor", "Prioridade"]]
            for d in dividas['detalhes']:
                div_data.append([d['nome'], f"R$ {d['valor']:.2f}", str(d['prioridade'])])

            div_table = Table(div_data, colWidths=[8*cm, 4*cm, 4*cm])
            div_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ff4757')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            story.append(div_table)
            story.append(Spacer(1, 20))

        # Recomendações da IA
        story.append(Paragraph("🤖 RECOMENDAÇÕES DA IA", heading_style))
        for acao in plano['acoes_recomendadas']:
            story.append(Paragraph(f"• {acao}", normal_style))

        story.append(Spacer(1, 30))
        story.append(Paragraph(
            f"<i>Relatório gerado automaticamente por NEXUS AI em {datetime.now().strftime('%d/%m/%Y %H:%M')}</i>",
            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
        ))

        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    def _gerar_pdf_html(self, mes_ref, saldo, dividas, reserva, plano, lancamentos, parcelas, contas):
        """Fallback: gera HTML que pode ser convertido a PDF pelo navegador"""
        mes_nome = self._mes_nome(mes_ref)

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Relatório {mes_nome}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
h1 {{ color: #1a1a2e; text-align: center; }}
h2 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 5px; margin-top: 30px; }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
th {{ background: #00d4ff; color: white; padding: 10px; text-align: left; }}
td {{ padding: 8px 10px; border-bottom: 1px solid #ddd; }}
tr:nth-child(even) {{ background: #f8f9fa; }}
.resumo {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0; }}
.resumo-item {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #ddd; }}
.footer {{ text-align: center; color: #888; font-size: 0.85em; margin-top: 40px; }}
.positive {{ color: #00ff88; }}
.negative {{ color: #ff4757; }}
</style>
</head>
<body>
<h1>📊 RELATÓRIO FINANCEIRO</h1>
<h3 style="text-align:center;color:#888">{mes_nome}</h3>

<h2>📈 Resumo Executivo</h2>
<div class="resumo">
<div class="resumo-item"><span>Receita Total</span><span><b>R$ {saldo['receita_total']:.2f}</b></span></div>
<div class="resumo-item"><span>Contas Fixas</span><span>R$ {saldo['contas_pendentes']:.2f}</span></div>
<div class="resumo-item"><span>Gastos Variáveis</span><span>R$ {saldo['gastos_mes']:.2f}</span></div>
<div class="resumo-item"><span>Parcelas</span><span>R$ {saldo['parcelas_mes']:.2f}</span></div>
<div class="resumo-item"><span><b>Saldo Projetado</b></span><span class="{'positive' if saldo['saldo_projetado'] >= 0 else 'negative'}"><b>R$ {saldo['saldo_projetado']:.2f}</b></span></div>
<div class="resumo-item"><span>Dívida Total</span><span class="negative">R$ {dividas['total_divida']:.2f}</span></div>
<div class="resumo-item"><span>Reserva</span><span>R$ {reserva['atual']:.2f} / R$ {reserva['meta']:.2f} ({reserva['percentual']:.1f}%)</span></div>
</div>

<h2>📋 Contas Fixas</h2>
<table>
<tr><th>Conta</th><th>Valor</th><th>Vencimento</th><th>Status</th></tr>
"""
        for c in contas:
            html += f"<tr><td>{c.nome}</td><td>R$ {c.valor:.2f}</td><td>Dia {c.vencimento}</td><td>{'✅ Paga' if c.pago else '⏳ Aberta'}</td></tr>
"

        html += "</table>
"

        if lancamentos:
            html += "<h2>💸 Lançamentos do Mês</h2>
<table>
"
            html += "<tr><th>Data</th><th>Descrição</th><th>Categoria</th><th>Valor</th></tr>
"
            for l in lancamentos:
                html += f"<tr><td>{l.data.strftime('%d/%m')}</td><td>{l.descricao}</td><td>{l.categoria}</td><td>R$ {l.valor:.2f}</td></tr>
"
            html += "</table>
"

        if dividas['total_divida'] > 0:
            html += "<h2>💳 Dívidas</h2>
<table>
"
            html += "<tr><th>Credor</th><th>Valor</th><th>Prioridade</th></tr>
"
            for d in dividas['detalhes']:
                html += f"<tr><td>{d['nome']}</td><td>R$ {d['valor']:.2f}</td><td>{d['prioridade']}</td></tr>
"
            html += "</table>
"

        html += "<h2>🤖 Recomendações da IA</h2>
<ul>
"
        for acao in plano['acoes_recomendadas']:
            html += f"<li>{acao}</li>
"
        html += "</ul>
"

        html += f"""
<div class="footer">
<p>Relatório gerado automaticamente por NEXUS AI</p>
<p>{datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
</div>
</body>
</html>"""

        return html.encode('utf-8')

    def _mes_nome(self, mes_ref):
        y, m = mes_ref.split("-")
        nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        return f"{nomes[int(m)-1]} de {y}"
