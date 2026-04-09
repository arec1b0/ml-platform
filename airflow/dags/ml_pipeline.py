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
        import os
        import mlflow
        from mlflow.tracking import MlflowClient

        ref_path = '/opt/airflow/reports/reference_data.parquet'
        os.makedirs('/opt/airflow/reports', exist_ok=True)
        
        MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow.set_tracking_uri(MLFLOW_URI)
        client = MlflowClient()
        
        try:
            model_name = "toxicity-classifier"
            latest = client.get_latest_versions(model_name, stages=["Production"])[0]
            client.download_artifacts(latest.run_id, "data/reference_data.parquet", "/opt/airflow/reports/")
            
            # The downloaded file is saved at /opt/airflow/reports/data/reference_data.parquet
            downloaded_path = "/opt/airflow/reports/data/reference_data.parquet"
            if os.path.exists(downloaded_path):
                # Move to standard path
                os.rename(downloaded_path, ref_path)
                
            print("Successfully downloaded reference dataset from MLflow.")
        except Exception as e:
            print(f"Error downloading from MLflow: {e}")
            raise Exception("Cannot proceed without baseline dataset.")
            
        return ref_path

    @task
    def extract_production_data_task():
        import os
        import json
        import pandas as pd

        log_path = '/opt/airflow/reports/predictions.jsonl'
        prod_path = '/opt/airflow/reports/production_data.parquet'
        
        if not os.path.exists(log_path):
            print(f"No prediction logs found at {log_path}. Creating an empty dataframe.")
            prod_data = pd.DataFrame(columns=['text_length', 'num_words', 'prediction_score'])
        else:
            data = []
            with open(log_path, 'r') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
            prod_data = pd.DataFrame(data)
            
            # Clear the file after reading (Log rotation)
            with open(log_path, 'w') as f:
                pass
            print(f"Cleared log file {log_path}")
            
        prod_data.to_parquet(prod_path)
        print("Production data extracted and saved.")
        return prod_path

    @task
    def calculate_drift_task(ref_path: str, prod_path: str):
        import pandas as pd
        from evidently.report import Report
        from evidently.metric_preset import DataDriftPreset
        from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

        ref_data = pd.read_parquet(ref_path)
        prod_data = pd.read_parquet(prod_path)

        if prod_data.empty:
            print("Production data is empty. Skipping drift calculation.")
            return

        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=ref_data, current_data=prod_data)
        
        report_dict = report.as_dict()
        dataset_drift = None
        share_of_drifted_columns = None
        for metric in report_dict['metrics']:
            if metric['metric'] == 'DatasetDriftMetric':
                dataset_drift = metric['result']['dataset_drift']
                share_of_drifted_columns = metric['result']['share_of_drifted_columns']

        if dataset_drift is not None:
            registry = CollectorRegistry()
            g_drift = Gauge('evidently_dataset_drift', 'Boolean indicating if dataset drift is detected (1) or not (0)', registry=registry)
            g_drift.set(1 if dataset_drift else 0)
            
            g_share = Gauge('evidently_share_of_drifted_columns', 'Share of drifted columns', registry=registry)
            g_share.set(share_of_drifted_columns)
            
            try:
                push_to_gateway('pushgateway:9091', job='evidently_drift', registry=registry)
                print("Pushed Evidently metrics to Pushgateway")
            except Exception as e:
                print(f"Failed to push metrics to Pushgateway: {e}")
        
        report_path = '/opt/airflow/reports/toxicity_drift_report.html'
        report.save_html(report_path)
        print(f"Drift report generated at {report_path}")

    # Define task dependencies
    ref_path = prepare_data_task()
    prod_path = extract_production_data_task()
    calculate_drift_task(ref_path, prod_path)

dag_instance = data_prep_and_drift_monitoring()
