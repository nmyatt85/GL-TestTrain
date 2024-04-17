FROM python:3.10-slim-bookworm

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

# Install non python dependencies
RUN apt-get update
RUN apt-get install -y libpq-dev gcc curl gpg

# Fetch Amazon RDS certificate chain
RUN curl https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o /usr/local/share/amazon-certs.pem
RUN chmod a=r /usr/local/share/amazon-certs.pem

# Install MSSQL ODBC 18 Driver
RUN mkdir -m 0755 -p /etc/apt/keyrings/
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg
RUN echo "deb [signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" | tee /etc/apt/sources.list.d/mssql-release.list
RUN apt-get update
RUN ACCEPT_EULA=Y apt-get install -y msodbcsql18

# modify openssl config to allow TLSv1 connection for TransitMaster server
RUN sed -i 's/\[openssl_init\]/# [openssl_init]/' /etc/ssl/openssl.cnf
RUN echo '\n\n[openssl_init]\nssl_conf = ssl_sect\n\n[ssl_sect]\nsystem_default = ssl_default_sect\n\n[ssl_default_sect]\nMinProtocol = TLSv1\nCipherString = DEFAULT@SECLEVEL=0\n' >> /etc/ssl/openssl.cnf

# Install poetry
RUN pip install -U pip
RUN pip install "poetry==1.7.1"

# copy poetry and pyproject files and install dependencies
WORKDIR /lamp/
COPY poetry.lock poetry.lock
COPY pyproject.toml pyproject.toml

# Tableau dependencies for arm64 cannot be resolved (since salesforce doesn't
# support them yet). For that buildplatform build without those dependencies
ARG TARGETARCH BUILDPLATFORM TARGETPLATFORM
RUN echo "Installing python dependencies for build: ${BUILDPLATFORM} target: ${TARGETPLATFORM}"
RUN if [ "$TARGETARCH" = "arm64" ]; then \
    poetry install --without tableau --no-interaction --no-ansi -v ;\
    else poetry install --no-interaction --no-ansi -v ;\
    fi

# Copy src directory to run against and build lamp py
COPY src src
COPY alembic.ini alembic.ini
RUN poetry install --no-dev --no-interaction --no-ansi -v
