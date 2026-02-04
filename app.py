import streamlit as st
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Consensus Validator", page_icon="⚖️", layout="wide")

st.title("⚖️ AI Consensus Validator")
st.markdown("Achieve objective truth by letting models debate each other.")

with st.sidebar:
    st.header("Credentials")
    with st.expander("Configure API Keys", expanded=True):
        openai_key = st.text_input("OpenAI Key", type="password")
        if openai_key: os.environ["OPENAI_API_KEY"] = openai_key
        anthropic_key = st.text_input("Anthropic Key", type="password")
        if anthropic_key: os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        google_key = st.text_input("Google Gemini Key", type="password")
        if google_key: os.environ["GEMINI_API_KEY"] = google_key
        groq_key = st.text_input("Groq Key", type="password")
        if groq_key: os.environ["GROQ_API_KEY"] = groq_key

    st.divider()
    st.header("Validator Configuration")

    AVAILABLE_MODELS = [
        "gpt-4o",
        "gpt-3.5-turbo",
        "claude-3-5-sonnet-20240620",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
        "qwen/qwen3-32b",
        "moonshotai/kimi-k2-instruct-0905",
        "openai/gpt-oss-120b"
    ]

    selected_debaters = st.multiselect(
        " Select Debaters:",
        options=AVAILABLE_MODELS,
        default=["moonshotai/kimi-k2-instruct-0905", "openai/gpt-oss-120b"]
    )

    selected_judge = st.selectbox(
        "⚖️ Select Validator:",
        options=AVAILABLE_MODELS,
        index=4  # Defaults to gemini-2.5-flash
    )

    if len(selected_debaters) < 2:
        st.warning("⚠️ Please select at least 2 debaters.")


if openai_key or anthropic_key or google_key or groq_key:
    from graph_validator import graph_app
else:
    st.info("👈 Please enter your API Keys in the sidebar to start.")
    st.stop()
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
question = st.chat_input("Enter your question")

if question and len(selected_debaters) >= 2:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    initial_state = {
        "question": question,
        "results": [],
        "iteration": 0,
        "verdict": "",
        "debater_models": selected_debaters,
        "judge_model": selected_judge
    }
    with st.chat_message("assistant"):
        status_box = st.container()
        try:
            for event in graph_app.stream(initial_state):
                if "debater" in event:
                    data = event["debater"]
                    iteration = data["iteration"] - 1

                    with status_box:
                        st.subheader(f" Debate Round #{iteration}")
                        cols = st.columns(len(data["results"]))

                        for idx, res in enumerate(data["results"]):
                            with cols[idx]:
                                with st.expander(f"{res['model']}", expanded=True):
                                    st.caption(res['response'])

                if "judge" in event:
                    verdict = event["judge"]["verdict"]
                    with status_box:
                        st.divider()
                        st.caption(f"⚖️ Judge **{selected_judge}** has deliberated.")
                        if "CONSENSUS" not in verdict:
                            st.warning("⚠️ Disagreement detected. Checking with models again...")
                            st.write(verdict)
            st.divider()

            if "CONSENSUS" in verdict:
                st.success(f"✅ Final Verdict (Validated by {selected_judge})")
                clean_verdict = verdict.replace("CONSENSUS", "").strip()
                st.markdown(f"**{clean_verdict}**")
                final_text = f"**✅ Verdict:**\n\n{clean_verdict}"
            else:
                st.error("❌ Consensus was not reached after maximum rounds.")
                st.write("Last validator remarks:")
                st.write(verdict)
                final_text = f"**❌ No Consensus:**\n\n{verdict}"
            st.session_state.messages.append({"role": "assistant", "content": final_text})
        except Exception as e:
            st.error(f"An error occurred during execution: {e}")
            st.info("Tip: Check that you provided the API Key for the specific models you selected.")

elif question and len(selected_debaters) < 2:
    st.error("Please select at least 2 models in the sidebar to start the debate.")