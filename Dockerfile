# Set the default port (can be overridden)
ARG PORT=443

# Use the Cypress browsers base image
FROM cypress/browsers:latest
FROM rapidfort/python-chromedriver

# Install Python 3
RUN apt-get update && apt-get install -y python3 python3-pip

# Set up the Python environment
RUN echo $(python3 -m site --user_base)

# Copy requirements file
COPY req.txt .

# Update PATH for local bin
ENV PATH="/home/root/.local/bin:${PATH}"

# Install Python packages
RUN pip install --no-cache-dir -r req.txt --break-system-packages

# Copy the rest of the application code
COPY . .

# Command to run your application
CMD python3 main.py $PORT
