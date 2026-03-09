FROM python:3.13-slim

# Desabilita geração de .pyc e habilita log unbuffered (essencial no Docker)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependências em camada separada para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código-fonte
COPY . .

# Ponto de entrada: inicia o scheduler como módulo Python
CMD ["python", "-m", "scheduler.app"]
