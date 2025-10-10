# Estágio 1: Build
# Usamos uma imagem Python oficial e específica para garantir consistência.
# A tag 'slim' resulta em uma imagem menor.
FROM python:3.11-slim AS builder

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia os arquivos de dependência da aplicação.
COPY requirements.txt .

# Instala as dependências em um ambiente virtual dentro da imagem
# Usar --no-cache-dir reduz o tamanho da imagem
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Estágio 2: Final
# Partimos de uma imagem limpa para a versão final, reduzindo o tamanho
# e a superfície de ataque ao não incluir ferramentas de build.
FROM python:3.11-slim

# Cria um usuário não-root para executar a aplicação.
# Rodar como não-root é uma prática de segurança fundamental.
RUN addgroup --system nonroot && adduser --system --ingroup nonroot nonroot

# Define o diretório de trabalho
WORKDIR /app

# Copia o ambiente virtual com as dependências instaladas do estágio anterior
COPY --from=builder /opt/venv /opt/venv

# Copia o código da aplicação para o diretório de trabalho
COPY . .

# Define o usuário não-root como o usuário padrão para executar a aplicação
USER nonroot

# Expõe a porta que o Gunicorn irá usar
EXPOSE 8000

# Define a variável de ambiente para que o Python encontre os pacotes no venv
ENV PATH="/opt/venv/bin:$PATH"

# Comando para iniciar a aplicação usando Gunicorn.
# 'run:app' aponta para a variável 'app' no arquivo 'run.py'.
# O bind 0.0.0.0:8000 faz o container ser acessível externamente.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "run:app"]