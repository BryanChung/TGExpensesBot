# Use latest Python slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Make sure Python output is unbuffered
ENV PYTHONUNBUFFERED=1

# Run the correct bot file
CMD ["python", "expenses_bot.py"]
