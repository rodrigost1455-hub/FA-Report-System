# ============================================================
# Dockerfile — FA Report Backend
# Para Railway (Python 3.11 + FastAPI + PyMuPDF)
# ============================================================
 
FROM python:3.11-slim
 
# PyMuPDF necesita estas libs del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*
 
WORKDIR /app
 
# Copiar e instalar dependencias primero (cache de layers)
COPY pyproject.toml ./
RUN pip install --no-cache-dir "poetry<2.0.0" && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --only main
 
# Copiar código fuente
COPY . .
 
# Crear carpeta para el template PDF
RUN mkdir -p app/pdf_engine/templates
 
# Puerto que Railway expone
EXPOSE 8000
 
# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
 
