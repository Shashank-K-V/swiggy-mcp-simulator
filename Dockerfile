FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
EXPOSE 8790
CMD ["swiggy-sim-server", "--host", "127.0.0.1", "--port", "8790"]

