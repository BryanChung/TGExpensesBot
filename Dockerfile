# Use the official Python image
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set environment variables (optional, you can set secrets in Fly.io)
ENV PYTHONUNBUFFERED=1

# Command to run your bot
CMD ["python", "bot.py"]
