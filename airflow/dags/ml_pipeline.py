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
        import pandas as pd
        import numpy as np

        ref_path = '/opt/airflow/reports/reference_data.parquet'
        
        # Fallback reference dataset if it doesn't exist
        if not os.path.exists(ref_path):
            num_records = 500
            ref_data = pd.DataFrame({
                'text_length': np.random.normal(50, 15, num_records),
                'num_words': np.random.normal(10, 3, num_records),
                'prediction_score': np.random.normal(0.2, 0.1, num_records),
            })
            ref_data['text_length'] = ref_data['text_length'].clip(lower=1)
            ref_data['num_words'] = ref_data['num_words'].clip(lower=1)
            ref_data['prediction_score'] = ref_data['prediction_score'].clip(lower=0, upper=1)
            
            os.makedirs('/opt/airflow/reports', exist_ok=True)
            ref_data.to_parquet(ref_path)
            print("Fallback reference data created.")
            
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
