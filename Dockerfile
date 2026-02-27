FROM python:3.12-slim

ENV LANG C.UTF-8

RUN apt-get update && apt-get install -y \
    git \
    gcc \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libldap2-dev \
    libsasl2-dev \
    libjpeg-dev \
    zlib1g-dev \
    wkhtmltopdf \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g rtlcss less less-plugin-clean-css

WORKDIR /opt/odoo

COPY odoo /opt/odoo

RUN pip install --upgrade pip && pip install -r requirements.txt

CMD ["python3", "odoo-bin", "-c", "/etc/odoo/odoo.conf"]