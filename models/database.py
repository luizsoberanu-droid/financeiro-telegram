from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

# =========================
# MODELOS
# =========================

class Config(Base):
    __tablename__ = 'config'
    id = Column(Integer, primary_key=True)
    receita_fixa = Column(Float, default=5300.0)
    receita_extra = Column(Float, default=0.0)
    meta_reserva = Column(Float, default=12000.0)
    reserva_atual = Column(Float, default=0.0)
    viagem_meta = Column(Float, default=0.0)
    viagem_atual = Column(Float, default=0.0)
    modo = Column(String, default="ataque_rigido")
    updated_at = Column(DateTime, default=datetime.utcnow)

class ContaFixa(Base):
    __tablename__ = 'contas_fixas'
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    valor = Column(Float, nullable=False)
    vencimento = Column(Integer, nullable=False)
    categoria = Column(String, default="geral")
    pago = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Cartao(Base):
    __tablename__ = 'cartoes'
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    vencimento = Column(Integer, nullable=False)
    melhor_dia_compra = Column(Integer, nullable=False)
    limite_ideal = Column(Float, default=200.0)
    pago = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Divida(Base):
    __tablename__ = 'dividas'
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    valor = Column(Float, nullable=False)
    ordem_prioridade = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Limite(Base):
    __tablename__ = 'limites'
    id = Column(Integer, primary_key=True)
    categoria = Column(String, nullable=False)
    valor = Column(Float, nullable=False)

class Lancamento(Base):
    __tablename__ = 'lancamentos'
    id = Column(Integer, primary_key=True)
    data = Column(DateTime, default=datetime.utcnow)
    mes_ref = Column(String, nullable=False)
    descricao = Column(String, nullable=False)
    categoria = Column(String, nullable=False)
    valor = Column(Float, nullable=False)
    forma_pagamento = Column(String, default="dinheiro")
    cartao = Column(String, nullable=True)
    fatura_mes_ref = Column(String, nullable=True)
    fatura_vencimento = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Parcela(Base):
    __tablename__ = 'parcelas'
    id = Column(Integer, primary_key=True)
    descricao = Column(String, nullable=False)
    cartao = Column(String, nullable=False)
    valor = Column(Float, nullable=False)
    parcela_atual = Column(Integer, nullable=False)
    total_parcelas = Column(Integer, nullable=False)
    mes_ref = Column(String, nullable=False)
    vencimento = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Conversa(Base):
    __tablename__ = 'conversas'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'user' ou 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Alerta(Base):
    __tablename__ = 'alertas'
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, nullable=False)
    tipo = Column(String, nullable=False)  # 'gasto', 'vencimento', 'meta', 'divida'
    mensagem = Column(Text, nullable=False)
    enviado = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# =========================
# ENGINE E SESSION
# =========================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///nexus.db")
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

    session = SessionLocal()

    # Seed inicial se estiver vazio
    if session.query(Config).first() is None:
        session.add(Config())

    if session.query(ContaFixa).count() == 0:
        contas_seed = [
            ContaFixa(nome="casa", valor=732.92, vencimento=10, categoria="moradia"),
            ContaFixa(nome="carro", valor=1469.70, vencimento=15, categoria="financiamento"),
            ContaFixa(nome="condominio", valor=365.0, vencimento=5, categoria="moradia"),
            ContaFixa(nome="faculdade", valor=360.0, vencimento=20, categoria="educacao"),
            ContaFixa(nome="faculdade_esposa", valor=200.0, vencimento=20, categoria="educacao"),
            ContaFixa(nome="internet", valor=220.0, vencimento=15, categoria="servicos"),
            ContaFixa(nome="luz", valor=270.0, vencimento=25, categoria="servicos"),
            ContaFixa(nome="ipva", valor=1161.0, vencimento=10, categoria="veiculo"),
        ]
        session.add_all(contas_seed)

    if session.query(Cartao).count() == 0:
        cartoes_seed = [
            Cartao(nome="samsung", vencimento=15, melhor_dia_compra=11),
            Cartao(nome="santander", vencimento=15, melhor_dia_compra=11),
            Cartao(nome="nubank", vencimento=1, melhor_dia_compra=30),
        ]
        session.add_all(cartoes_seed)

    if session.query(Divida).count() == 0:
        dividas_seed = [
            Divida(nome="negativo", valor=2999.94, ordem_prioridade=5),
            Divida(nome="ipva", valor=1161.0, ordem_prioridade=4),
            Divida(nome="samsung", valor=134.0, ordem_prioridade=3),
            Divida(nome="santander", valor=996.12, ordem_prioridade=2),
            Divida(nome="nubank", valor=1006.05, ordem_prioridade=1),
        ]
        session.add_all(dividas_seed)

    if session.query(Limite).count() == 0:
        limites_seed = [
            Limite(categoria="lazer", valor=100.0),
            Limite(categoria="combustivel", valor=320.0),
            Limite(categoria="extras", valor=100.0),
        ]
        session.add_all(limites_seed)

    session.commit()
    session.close()
    print("✅ Banco de dados inicializado com dados padrão")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
