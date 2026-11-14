FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.3.5 fastapi==0.115.12 httpx==0.28.1 bandit==1.8.3
USER 65534:65534
WORKDIR /repo
ENV PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
