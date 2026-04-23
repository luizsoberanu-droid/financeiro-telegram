# ============================================
# NEXUS AI v2.3 - Dockerfile para Render
# ============================================
# Build: docker build -t nexus-ai .
# Run:   docker run -p 5000:5000 nexus-ai
# ============================================

# Etapa 1: Build
FROM python:3.11-slim as builder

# Instalar dependências de build
RUN apt-get update && apt-get install -y --no-install-recommends     gcc     libpq-dev     && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements primeiro (cache do Docker)
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Etapa 2: Runtime (imagem final menor)
# ============================================
FROM python:3.11-slim

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PYTHONFAULTHANDLER=1     PATH=/root/.local/bin:$PATH     PORT=5000

# Instalar dependências de runtime mínimas
RUN apt-get update && apt-get install -y --no-install-recommends     libpq5     curl     && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar dependências instaladas do builder
COPY --from=builder /root/.local /root/.local

# Copiar código da aplicação
COPY . .

# Criar diretório para o banco de dados SQLite
RUN mkdir -p /app/data

# Health check - verifica se a aplicação está respondendo
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3     CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Expor a porta
EXPOSE $PORT

# Comando para iniciar a aplicação
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
