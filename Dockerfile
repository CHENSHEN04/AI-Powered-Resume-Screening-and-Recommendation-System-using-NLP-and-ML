# ==============================================================================
# Dockerfile for AI-Powered Resume Screening & Recommendation System
# ==============================================================================

# Use an official lightweight Python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8501

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (including libmagic for file type detection)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
# We use the CPU version of PyTorch to keep the image size small and suitable for free-tier deployments
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Pre-download the spaCy model to speed up container startup
RUN python -m spacy download en_core_web_sm

# Copy the rest of the application code
COPY . .

# Expose the Streamlit port
EXPOSE 8501

# Run the Streamlit application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
