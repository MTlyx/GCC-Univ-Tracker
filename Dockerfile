FROM python:3.9-slim

WORKDIR /app

# Installation des dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY *.py .

# Création du dossier data
RUN mkdir -p data

# Lancement du bot
CMD ["python", "-u", "main.py"]
