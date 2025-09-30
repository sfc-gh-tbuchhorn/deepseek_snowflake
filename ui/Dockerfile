# Use the official lightweight Python image as the base image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy all files from the host machine to the working directory in the container
COPY requirements.txt .

# Install required Python packages listed in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port 8501 for the Streamlit app (Streamlit default port)
EXPOSE 8501

# Define the command to run the Streamlit application on port 8500, accessible from any IP
ENTRYPOINT ["streamlit", "run", "ui.py", "--server.port=8500", "--server.address=0.0.0.0"]
