FROM python:3.11-slim

WORKDIR /app

# Installer les dépendances système nécessaires pour pyodbc + ODBC Driver 17
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    && mkdir -p /etc/apt/keyrings \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copier les dépendances Python et les installer
COPY requirements_docker.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements_docker.txt
# Copier le code du projet
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app/1_account_transaction_xml_generator.py", "--server.port=8501", "--server.address=0.0.0.0"]