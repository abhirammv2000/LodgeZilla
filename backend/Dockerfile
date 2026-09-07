FROM python:3.11-slim

WORKDIR /myapp

# Install dependencies first so the layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "run.py"]
