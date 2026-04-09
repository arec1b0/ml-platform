import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset

default_args = {
    'owner': 'ml-platform',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

@dag(
    default_args=default_args,
    schedule_interval='@daily',
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['mlops', 'monitoring'],
)
def data_prep_and_drift_monitoring():
    
    @task
    def prepare_data_task():
        # Simulate loading and preparing training/reference data
        # Feature extraction (e.g., text length, num words) could happen here
        num_records = 1000
        ref_data = pd.DataFrame({
            'text_length': np.random.normal(50, 15, num_records),
            'num_words': np.random.normal(10, 3, num_records),
            'prediction_score': np.random.normal(0.2, 0.1, num_records), # mostly non-toxic
        })
        ref_data.to_parquet('/opt/airflow/reports/reference_data.parquet')
        print("Reference data prepared and saved.")
        return "/opt/airflow/reports/reference_data.parquet"

    @task
    def extract_production_data_task():
        # Simulate extracting today's data from production (gateway)
        num_records = 200
        # Injecting drift: longer comments and more toxicity in production today
        prod_data = pd.DataFrame({
            'text_length': np.random.normal(80, 20, num_records), 
            'num_words': np.random.normal(15, 5, num_records),
            'prediction_score': np.random.normal(0.6, 0.2, num_records), 
        })
        prod_data.to_parquet('/opt/airflow/reports/production_data.parquet')
        print("Production data extracted and saved.")
        return "/opt/airflow/reports/production_data.parquet"

    @task
    def calculate_drift_task(ref_path: str, prod_path: str):
        ref_data = pd.read_parquet(ref_path)
        prod_data = pd.read_parquet(prod_path)

        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=ref_data, current_data=prod_data)
        
        report_path = '/opt/airflow/reports/toxicity_drift_report.html'
        report.save_html(report_path)
        print(f"Drift report generated at {report_path}")

    # Define task dependencies
    ref_path = prepare_data_task()
    prod_path = extract_production_data_task()
    calculate_drift_task(ref_path, prod_path)

dag_instance = data_prep_and_drift_monitoring()
