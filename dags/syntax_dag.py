from airflow.sdk import dag, task
from airflow.providers.standard.operators.hitl import HITLOperator


@dag
def syntax_dag():

    @task
    def get_message():
        return "Make a wise choice..."

    _get_message_task = get_message()

    _syntax_example_hitl_task = HITLOperator(
        task_id="syntax_example_hitl_task",
        subject="Choose your starter Pokemon",  # templatable
        body=_get_message_task,  # templatable
        options=["Bulbasaur", "Charmander", "Squirtle"],  # cannot be empty!
        defaults=["Charmander"],
        params={"Message to your new Pokemon": "..."},
    )

    @task
    def print_response(hitl_output: dict):
        print(f"Starter Pokemon: {hitl_output['chosen_options']}")
        print(
            f"Message to your new Pokemon: ${hitl_output['params_input']['Message to your new Pokemon']}"
        )

    _print_response = print_response(_syntax_example_hitl_task.output)


syntax_dag()
