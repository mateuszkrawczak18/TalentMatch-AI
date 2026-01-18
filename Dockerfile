FROM python:3.10-slim

WORKDIR /app

# Instalacja narzędzi systemowych
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# Kopiowanie zależności i instalacja
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie kodu
COPY . .

# Wystawienie portu
EXPOSE 8000

# Start API
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]