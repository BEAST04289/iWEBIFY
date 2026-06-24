FROM python:3.11-slim

WORKDIR /app

# Install pip and dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .

# Copy source code
COPY . .

# Create sessions directory
RUN mkdir -p /tmp/iwebify_sessions

EXPOSE 7860

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]
