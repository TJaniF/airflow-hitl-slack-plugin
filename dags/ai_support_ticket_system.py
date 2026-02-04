from airflow.providers.standard.operators.hitl import (
    HITLOperator,
)
from airflow.sdk import dag, task, Param, chain, Asset
from datetime import timedelta
import random
from typing import Literal
from airflow_ai_sdk.models.base import BaseModel
from pydantic_ai import Agent
from include.custom_functions import read_all_decision_traces, check_the_roadmap


class TicketResponse(BaseModel):
    summary: str
    response: str
    priority: Literal["low", "medium", "high"]
    confidence_score: float
    suggested_tags: list[str]


customer_success_agent = Agent(
    model="gpt-4o-mini",
    system_prompt="""
    You are friendly and helpful support agent generating answers to tickets.
    Make sure to address the customer by name in the response.

    Tools: 
    - `read_all_decision_traces`: Read all decision traces for previous reviews of your responses.
    - `check_the_roadmap`: Check the roadmap for the requested feature.
    """,
    output_type=TicketResponse,
    tools=[read_all_decision_traces, check_the_roadmap],
)


@dag
def ai_support_ticket_system():

    @task
    def fetch_pending_ticket() -> list[dict]:
        from include.custom_functions import get_open_tickets

        tickets = get_open_tickets(1)
        return tickets[0]

    _fetch_pending_ticket = fetch_pending_ticket()

    @task.agent(agent=customer_success_agent)
    def generate_ai_response(ticket: dict):
        import json

        ticket_str = json.dumps(ticket)
        return ticket_str

    _generate_ai_response = generate_ai_response(ticket=_fetch_pending_ticket)

    @task
    def format_approval_request(ai_response: dict, original_ticket: dict):
        return {
            "ticket_info": f"**Ticket:** {original_ticket['ticket_id']}\n**Customer:** {original_ticket['customer']}\n**Subject:** {original_ticket['subject']}\n**Priority:** {original_ticket['priority']}",
            "summary": ai_response["summary"],
            "ai_response": ai_response["response"],
            "confidence": ai_response["confidence_score"],
            "priority": ai_response["priority"],
            "suggested_tags": ai_response["suggested_tags"],
            "metadata": ai_response,
            "original_ticket": original_ticket,
        }

    _format_approval_request = format_approval_request(
        ai_response=_generate_ai_response, original_ticket=_fetch_pending_ticket
    )

    # Human approval step
    _review_ai_response = HITLOperator(
        task_id="review_ai_response",
        subject="🎫 AI Support Response Ready for Review",
        body="""**Please review the AI-generated support ticket response below:**

{{ ti.xcom_pull(task_ids='format_approval_request')['ticket_info'] }}

**AI Summary:**
{{ ti.xcom_pull(task_ids='format_approval_request')['summary'] }}

**AI Suggested Priority:** {{ ti.xcom_pull(task_ids='format_approval_request')['priority'] }}
**AI Confidence:** {{ "%.0f" | format(ti.xcom_pull(task_ids='format_approval_request')['confidence'] * 100) }}%
**Suggested Tags:** {{ ti.xcom_pull(task_ids='format_approval_request')['suggested_tags'] | join(', ') }}

**AI Response:**

--------------------------------

{{ ti.xcom_pull(task_ids='format_approval_request')['ai_response'] }}

--------------------------------

**Instructions:**
- **Approve AI Response**: Send the AI response to the customer - optionall add a review of the AI response to the notes field
- **Manual Response**: Send the manual response provided to the notes field 
- **Escalate to CRE**: Escalate to the CRE team - add a reason for escalation to the notes field

Please review for accuracy, tone, and completeness.""",
        options=[
            "Approve AI Response",
            "Respond Manually",
            "Escalate to CRE",
        ],
        multiple=False,
        defaults=["Escalate to CRE"],
        params={
            "Reason for decision": Param(type=["string", "null"], default="..."),
            "Manual response": Param(type=["string", "null"], default="..."),
        },
        execution_timeout=timedelta(
            hours=4
        ),  # after 4 hours the default option will be selected
    )

    @task(outlets=[Asset("new_decision")])
    def process_response(hitl_output: dict):
        if hitl_output["chosen_options"][0] == "Respond Manually":
            print("Respond Manually")
            print(hitl_output["params_input"]["Reason for decision"])
            print(hitl_output["params_input"]["Manual response"])
            return
        if hitl_output["chosen_options"][0] == "Approve AI Response":
            print("Approved AI Response")
            print(hitl_output["params_input"]["Reason for decision"])
            return
        if hitl_output["chosen_options"][0] == "Escalate to CRE":
            print("Escalate to CRE")
            print(hitl_output["params_input"]["Reason for decision"])
            return

    _process_response = process_response(hitl_output=_review_ai_response.output)

    chain(
        _format_approval_request,
        _review_ai_response,
        _process_response,
    )


ai_support_ticket_system()
