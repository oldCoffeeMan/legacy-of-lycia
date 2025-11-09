FROM python:3.14-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy psycopg2-binary alembic pydantic-settings python-dotenv redis jinja2 ruff mypy pytest "passlib[bcrypt]" "bcrypt<4.0.0" itsdangerous requests
EXPOSE 8000
CMD ["uvicorn", "src.lycia.app:app", "--host", "0.0.0.0", "--port", "8000"]
