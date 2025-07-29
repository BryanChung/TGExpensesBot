FROM python:3.13-slim

WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1

# Run your actual bot script
CMD ["python", "expenses_bot.py"]
