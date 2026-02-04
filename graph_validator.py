import os
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END
from groq import Groq
from google import genai
from openai import OpenAI
from anthropic import Anthropic

class AgentState(TypedDict):
    question: str
    results: List[Dict]
    verdict: str
    iteration: int
    debater_models: List[str]
    judge_model: str

def get_system_prompt():
    return """You are my assistant. Try to answer in a detailed manner without hallucinating. 
    If you dont know an answer it is better to say you dont know than to make something up."""

def call_openai(prompt, model):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key: return "Error: OPENAI_API_KEY not set."
    try:
        openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {e}"

def call_anthropic(prompt, model):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key: return "Error: ANTHROPIC_API_KEY not set."
    try:
        anthropic_client = Anthropic(api_key=api_key)
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=1024,
            system=get_system_prompt(),
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Anthropic Error: {e}"

def call_gemini(prompt, model):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return "Error: GEMINI_API_KEY not set."
    try:
        gemini_client = genai.Client(api_key=api_key)
        response = gemini_client.models.generate_content(
            model=model,
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Gemini Error: {e}"

def call_groq(prompt, model):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key: return "Error: GROQ_API_KEY not set."
    try:
        groq_client = Groq(api_key=api_key)
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            model=model
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Groq Error: {e}"

def call_model_router(prompt, model_name):
    if "gpt" in model_name and "oss" not in model_name:
        return call_openai(prompt, model_name)
    elif "claude" in model_name:
        return call_anthropic(prompt, model_name)
    elif "gemini" in model_name:
        return call_gemini(prompt, model_name)
    else:
        return call_groq(prompt, model_name)


def generate_responses(question, current_results, iteration, active_models):
    new_results = []

    if iteration == 0:
        for model in active_models:
            res = call_model_router(question, model)
            new_results.append({'model': model, 'response': res})
    else:
        for model in active_models:
            own_answer = next(r['response'] for r in current_results if r['model'] == model)
            other_answers = [r['response'] for r in current_results if r['model'] != model]

            prompt = get_debate_prompt(question, own_answer, other_answers)
            res = call_model_router(prompt, model)
            new_results.append({'model': model, 'response': res})

    return new_results

def get_debate_prompt(question, model_answer, other_answers):
    return f"""
    You originally answered the question "{question}" as follows:
    {model_answer}

    However, other models have provided different answers:
    {other_answers}. 

    Can you review your answer? If you think you are right, repeat it. If not, correct it. 
    You should stick to the facts and provide an answer about the question, dont answer with excuses or justifications.
    """

# --- NODES ---

def node_debater(state: AgentState):
    """
    This node is responsible for generating responses.
    """
    iteration = state['iteration']
    print(f"\n---  Iteration {iteration} ---")
    active_models = state['debater_models']
    new_results = generate_responses(
        state['question'],
        state.get('results', []),
        iteration,
        active_models
    )
    for res in new_results:
        print(f"\n Model: {res['model']}")
        print("-" * 60)
        print(res['response'][:100] + "...")  # Print preview only
        print("-" * 60)
    return {
        "results": new_results,
        "iteration": iteration + 1
    }

def node_validator(state: AgentState):
    """
    This node acts as the Validator.
    """
    print("\n---  The Judge is deliberating ---")
    question = state['question']
    responses = state['results']
    judge_model = state['judge_model']
    validator_prompt = f"""
    You are an expert AI evaluator. Compare these responses to the question: "{question}"
    Responses: {responses}

    1. If they consistently agree on the core facts/conclusion, start your response strictly with "CONSENSUS" followed by the final answer.
    2. If they disagree, describe the discrepancies. DO NOT use the word CONSENSUS.
    It is important that you dont answer the question that was raised to the models, you just judge if they agree or not.
    """
    try:
        verdict = call_model_router(validator_prompt, judge_model)
    except Exception as e:
        verdict = f"Error in validation: {str(e)}"
    print(f"\n📝 VERDICT:")
    if "CONSENSUS" in verdict:
        print("✅ CONSENSUS")
    else:
        print("❌ DISAGREEMENT")
    return {"verdict": verdict}

# --- ROUTER ---

def check_consensus(state: AgentState):
    if "CONSENSUS" in state['verdict']:
        return "approved"
    if state['iteration'] >= 3:
        print("--- 🛑 Iteration limit reached. Aborting ---")
        return "max_retries"
    return "rejected"

# --- GRAPH ---

def create_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("debater", node_debater)
    workflow.add_node("judge", node_validator)
    workflow.set_entry_point("debater")
    workflow.add_edge("debater", "judge")
    workflow.add_conditional_edges(
        "judge",
        check_consensus,
        {
            "approved": END,
            "max_retries": END,
            "rejected": "debater"
        }
    )
    return workflow.compile()

graph_app = create_graph()