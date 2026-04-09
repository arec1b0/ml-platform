FROM apache/airflow:2.9.1

COPY requirements.txt /requirements.txt

RUN pip install uv && uv pip install --system --no-cache -r /requirements.txt
