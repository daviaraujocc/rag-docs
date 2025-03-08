FROM python:3.11-slim AS compile-image

ARG EXTRA_BUILD_PACKAGES=""

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    ${EXTRA_BUILD_PACKAGES} \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS build-image
COPY --from=compile-image /opt/venv /opt/venv

ARG EXTRA_RUNTIME_PACKAGES=""
RUN if [ -n "${EXTRA_RUNTIME_PACKAGES}" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends ${EXTRA_RUNTIME_PACKAGES} && \
        rm -rf /var/lib/apt/lists/*; \
    fi

ENV PATH="/opt/venv/bin:$PATH"

ARG FILES="*.py"
COPY ${FILES} .

EXPOSE 6000

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker","--bind", "0.0.0.0:6000", "--workers", "1", "--timeout", "90", "main:app"]