# Base image 
# https://hub.docker.com/_/python
FROM python:3.13-slim

# Set the working directory  
WORKDIR /app  

# Install dependencies  
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application files  
COPY app.py .

# Command to run when the container starts  
CMD ["streamlit", "run", "app.py"]
