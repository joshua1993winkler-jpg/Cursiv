FROM python:3.11-slim
WORKDIR /app
COPY cursiv_v215/web/ ./cursiv_v215/web/
COPY cursiv_v215/__init__.py ./cursiv_v215/__init__.py
RUN pip install --no-cache-dir \
    fastapi==0.111.0 \
    "uvicorn[standard]==0.29.0" \
    PyJWT==2.8.0 \
    pydantic==2.7.1 \
    anthropic>=0.49.0
EXPOSE 8080
CMD uvicorn cursiv_v215.web.app:app --host 0.0.0.0 --port ${PORT:-8080}
