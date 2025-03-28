# Use Python base image
FROM python:3.10-slim

# Install OpenJDK and build dependencies
RUN apt-get update && \
    apt-get install -y default-jdk wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install JMeter
ENV JMETER_VERSION="5.6.3"
ENV JMETER_HOME="/opt/apache-jmeter-${JMETER_VERSION}"
ENV PATH="$JMETER_HOME/bin:$PATH"

RUN wget https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz && \
    tar -xzf apache-jmeter-${JMETER_VERSION}.tgz -C /opt && \
    rm apache-jmeter-${JMETER_VERSION}.tgz

# Set working directory
WORKDIR /app

# Copy application files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install "mcp[cli]<1.6.0" && \
    pip install --no-cache-dir -r requirements.txt

# Expose port (adjust if your server uses a different port)
EXPOSE 8000

# Run the server
CMD ["python", "jmeter_server.py"] 