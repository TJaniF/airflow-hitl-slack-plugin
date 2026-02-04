from airflow.sdk import dag, task
from datetime import datetime
@dag(
    start_date=datetime(2026, 1, 1),
    max_active_runs=1,
    schedule="@continuous"
)
def test_dag():

    @task
    def get_message():
        import time
        time.sleep(2)
        return "Make a wise choice..."

    _get_message_task = get_message()

test_dag()