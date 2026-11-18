FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860 BIND_HOST=0.0.0.0 HF_HOME=/app/.cache/huggingface
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 1000 appuser && mkdir -p /app/.cache && chown -R appuser:appuser /app
COPY --chown=appuser:appuser app.py engine.py search.py gunicorn.conf.py ./
COPY --chown=appuser:appuser data/ data/
COPY --chown=appuser:appuser templates/ templates/
COPY --chown=appuser:appuser static/ static/
USER appuser
EXPOSE 7860
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
