"""The chatbot loop. Requires a Gemini API key.
   Run with: python -m app.chatbot.agents"""

import os
import json
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

from app.chatbot.tools import FUNCTION_MAP, TOOL_SCHEMAS

GEMINI_API_KEYS = [value for value in [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GOOGLE_API_KEY"),
    os.getenv("GEMINI_API_KEY_ALT"),
] if value]

GEMINI_MODELS = []
user_model = os.getenv("GEMINI_MODEL")
if user_model:
    GEMINI_MODELS.append(user_model)

for default_model in [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
]:
    if default_model not in GEMINI_MODELS:
        GEMINI_MODELS.append(default_model)


def _build_client(api_key: str, model_name: str):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name,
        tools=list(FUNCTION_MAP.values())
    )
    model._api_key = api_key
    return model


CLIENTS = []
for key in GEMINI_API_KEYS:
    for model_name in GEMINI_MODELS:
        try:
            CLIENTS.append(_build_client(key, model_name))
        except Exception:
            continue

client = CLIENTS[0] if CLIENTS else None

SYSTEM_PROMPT = (
    "You are the Jazz Resource Platform AI Assistant, an internal assistant for querying and managing "
    "the resource database and sales pipeline.\n\n"
    "CONVERSATIONAL RULES:\n"
    "1. Greetings/small talk/questions about yourself: respond directly and briefly, no tools.\n"
    "2. Unrelated topics: say you're dedicated to the resource platform and can't help with that, no tools.\n"
    "3. Only call a tool for explicit resource/deal/funnel requests. If vague, ask for clarification instead of guessing arguments. Never invent or hallucinate data.\n"
    "4. Use conversation history to resolve pronouns/follow-ups; don't re-call a tool for info already fetched.\n"
    "5. If a tool returns an error or no matches, say so plainly -- never fill the gap from other context.\n"
    "6. If a tool returns {\"ambiguous\": true, \"matches\": [...]}, list the matches and ask the user to pick one -- never guess.\n"
    "7. Never start an answer with 'Based on the tool result' or similar meta-commentary -- state the answer directly.\n\n"
    "QUERY_RESOURCES IS YOUR MAIN TOOL for counts, sums/averages, and breakdowns:\n"
    "- COUNT: aggregate='count' with filters, e.g. query_resources(filters={\"practice\": \"Analytics & Insights\", \"billable_flag\": true}, aggregate=\"count\")\n"
    "- SUM/AVG: aggregate='sum'/'avg' + aggregate_field, e.g. query_resources(filters={\"practice\": \"...\"}, aggregate=\"sum\", aggregate_field=\"monthly_billing_usd\")\n"
    "- BREAKDOWN by a category (grade/practice/location/job_title/etc.), or MULTIPLE values of the same field at once (e.g. 'headcount in L1-L5', 'per practice'): use group_by -- ONE call, NEVER loop per value: query_resources(group_by=\"grade\", aggregate=\"count\")\n"
    "- Combine filters + group_by + aggregate freely, e.g. non-billable per grade: query_resources(filters={\"billable_flag\": false}, group_by=\"grade\", aggregate=\"count\"). For 'billable AND non-billable per grade', make two calls (one per billable_flag value) and present as one table.\n"
    "- filters supports: scalar equality, {\"gt\"/\"gte\"/\"lt\"/\"lte\"/\"ne\": X} for ranges, or a list for IN (e.g. {\"grade\": [\"L1\",\"L2\"]}).\n"
    "- Always report a result's 'total_count' field, not just the rows shown (list tools cap at 25).\n\n"
    "OTHER TOOLS:\n"
    "- ONE person by name: get_resource_summary. By emp_id: get_resource_by_id.\n"
    "- Everyone in a practice: get_resources_by_practice.\n"
    "- Flexible multi-criteria search/list/sort/date-range (e.g. 'who reports to X', 'top 5 earners', 'hired after March 2026'): search_resources -- use its dedicated parameters (line_manager, hrbp, sub_practice, project_client_squad, min/max_hire_date, sort_by/sort_order/limit, etc.), never stuff numeric/structured conditions into the free-text 'query' field.\n"
    "- For requests like 'resources without a job title', 'no job title', or 'missing title', treat them as a missing/blank job-title filter rather than a broad free-text search.\n"
    "- Sales pipeline: list_deals, get_funnel_summary, add_deal, delete_deal, get_funnel_history.\n"
    "- Change history for a person: get_resource_history.\n\n"
    "EDITS: call propose_change first and get an explicit 'yes' confirming the exact old/new value before calling apply_change. "
    "Editable fields: grade, resource_status, project_client_squad, line_manager, daily_rate_usd, billable_flag, practice, "
    "job_title, sub_practice, employee_type, billable_pct, hrbp, comments.\n\n"
    "The resource database has, per employee: emp_id, name, job title, line manager (+id), practice, sub-practice, grade, "
    "employee type, project/client/squad, billable flag/%, daily rate, days billed, monthly billing, engagement start, "
    "release date, resource status, hire date, HRBP, department, location, email, comments, data-quality flags -- "
    "you may read and report all of these.\n"
)


def get_system_prompt() -> str:
    from datetime import date
    today_str = date.today().isoformat()
    return SYSTEM_PROMPT + f"\n\nToday's date is: {today_str}."


def _generate_with_fallback(messages: list, *, stream: bool = False):
    if not CLIENTS:
        raise RuntimeError("No Gemini clients configured")

    payload = [
        {"role": "user", "parts": [get_system_prompt()]},
        *[
            {
                "role": "model" if msg["role"] == "assistant" else msg["role"],
                "parts": [msg["content"]]
            }
            for msg in messages[1:]
        ],
    ]

    last_error = None
    for client_model in CLIENTS:
        try:
            if hasattr(client_model, "_api_key"):
                genai.configure(api_key=client_model._api_key)
            
            import copy
            current_payload = copy.deepcopy(payload)
            
            while True:
                response = client_model.generate_content(
                    current_payload,
                    generation_config={"temperature": 0.2}
                )
                
                # Check for function calls in candidates
                function_calls = []
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.function_call:
                            function_calls.append(part.function_call)
                
                if not function_calls:
                    if stream:
                        return client_model.generate_content(
                            current_payload,
                            generation_config={"temperature": 0.2},
                            stream=True
                        )
                    return response
                
                # Append model response (with the function calls)
                current_payload.append(response.candidates[0].content)
                
                # Execute functions
                response_parts = []
                for function_call in function_calls:
                    name = function_call.name
                    args = dict(function_call.args)
                    
                    func = FUNCTION_MAP.get(name)
                    if func:
                        try:
                            result = func(**args)
                        except Exception as e:
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"Function '{name}' not found."}
                    
                    response_parts.append({
                        "function_response": {
                            "name": name,
                            "response": result if isinstance(result, dict) else {"result": result}
                        }
                    })
                
                # Append response turn
                current_payload.append({
                    "role": "user",
                    "parts": response_parts
                })
        except Exception as exc:
            last_error = exc
            print(f"Fallback model attempt failed ({type(exc).__name__}): {exc}")
            continue

    raise last_error or RuntimeError("All Gemini fallback attempts failed")


def ask(question: str, history: list = None) -> str:
    if not CLIENTS:
        return "Gemini API key is not configured. Please set the GEMINI_API_KEY environment variable in your .env file to enable the chatbot."
    messages = [
        {"role": "system", "content": get_system_prompt()}
    ]
    if history:
        for msg in history:
            role = "user" if msg.get("sender") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("text", "")})
    messages.append({"role": "user", "content": question})

    try:
        response = _generate_with_fallback(messages)
    except Exception as e:
        print(f"Primary model failed ({type(e).__name__}): {e}")
        if isinstance(e, google_exceptions.ResourceExhausted):
            return "The Gemini API is currently rate-limited or out of quota. Please wait a few minutes or use a paid/expanded Google AI quota."
        if isinstance(e, google_exceptions.PermissionDenied):
            return "The Gemini API key is not authorized for this request. Please check the key and its permissions."
        return "I'm currently having trouble reaching the Gemini model. Please try again in a few minutes."

    message_text = getattr(response, "text", "") or ""
    if not message_text:
        return "I couldn't generate a response right now."

    return message_text


async def ask_stream(question: str, history: list = None):
    if not CLIENTS:
        yield {"type": "answer", "content": "Gemini API key is not configured. Please set the GEMINI_API_KEY environment variable in your .env file to enable the chatbot."}
        return
    messages = [
        {"role": "system", "content": get_system_prompt()}
    ]
    if history:
        for msg in history:
            role = "user" if msg.get("sender") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("text", "")})
    messages.append({"role": "user", "content": question})

    yield {"type": "status", "content": "Thinking..."}
    try:
        response = _generate_with_fallback(messages, stream=False)
    except Exception as e:
        print(f"Primary model failed ({type(e).__name__}): {e}")
        if isinstance(e, google_exceptions.ResourceExhausted):
            yield {"type": "answer", "content": "The Gemini API is currently rate-limited or out of quota. Please wait a few minutes or use a paid/expanded Google AI quota."}
        elif isinstance(e, google_exceptions.PermissionDenied):
            yield {"type": "answer", "content": "The Gemini API key is not authorized for this request. Please check the key and its permissions."}
        else:
            yield {"type": "answer", "content": "I'm currently having trouble reaching the Gemini model. Please try again in a few minutes."}
        return

    message_text = getattr(response, "text", "") or ""
    if not message_text:
        yield {"type": "answer", "content": "I couldn't generate a response right now."}
        return

    yield {"type": "answer", "content": message_text}
    return


if __name__ == "__main__":
    print("Ask a question (Ctrl+C to quit):")
    cli_history = []
    while True:
        q = input("> ")
        response = ask(q, cli_history)
        print(response)
        cli_history.append({"sender": "user", "text": q})
        cli_history.append({"sender": "bot", "text": response})