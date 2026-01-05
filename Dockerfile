FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Questa riga è quella che copia il file cookies.txt nel server
COPY . . 
CMD ["python", "main.py"]
