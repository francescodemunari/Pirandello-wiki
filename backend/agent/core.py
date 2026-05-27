import json
from backend.agent.prompts import get_pirandello_system_prompt
from backend.agent.provider_manager import stream_chat, chat_once
from backend.tools.wiki_search import wiki_search
from backend.tools.memory_tools import MEMORY_TOOL_DEFINITIONS, execute_memory_tool
from backend.memory import user_memory as mem
from backend.memory.chat_history import get_summary

MAX_HISTORY = 6
MAX_MEMORY_TOOL_ITERS = 3

MEMORY_PROMPT_RULE = """
MEMORIA UTENTE: Hai strumenti save_user_fact, get_user_profile, delete_user_fact.
Quando l'interlocutore condivide informazioni personali stabili (nome, studi, preferenze, fatti biografici), salva un fatto conciso con save_user_fact prima o insieme alla risposta.
Non salvare ogni messaggio: solo fatti utili per dialoghi futuri. Non menzionare gli strumenti all'utente.
"""


def build_context(results: list[dict]) -> str:
    if not results:
        return ""
    lines = ["--- CONTESTO DALLA WIKI DI PIRANDELLO ---"]
    for r in results:
        lines.append(f"\n## {r['title']} (da {r['path']})")
        lines.append(r["preview"])
    lines.append("\n--- FINE CONTESTO ---\n")
    return "\n".join(lines)


async def chat_with_pirandello(user_message: str, history: list, session_id: str = None, provider: str = None):
    results = await wiki_search(user_message)
    context = build_context(results)

    system_prompt = get_pirandello_system_prompt()
    profile = mem.get_profile_summary()
    if profile:
        system_prompt += f"\n\n{profile}\n"
    system_prompt += MEMORY_PROMPT_RULE

    system_msg = {"role": "system", "content": system_prompt}

    summary_msg = None
    if session_id:
        summary_data = await get_summary(session_id)
        if summary_data:
            summary_text, _ = summary_data
            summary_msg = {
                "role": "system",
                "content": f"Riassunto impersonale del dialogo precedente (da tenere a mente per coerenza): {summary_text}",
            }

    context_msg = None
    if context:
        context_msg = {
            "role": "system",
            "content": f"Altri dettagli dalla tua wiki:\n\n{context}",
        }

    recent_history = history[-MAX_HISTORY:] if history else []
    user_msg = {"role": "user", "content": user_message}

    messages = [system_msg]
    if summary_msg:
        messages.append(summary_msg)
    if context_msg:
        messages.append(context_msg)
    messages.extend(recent_history)

    msg_lower = user_message.strip().lower()
    is_light = len(user_message.strip()) < 90 and any(
        k in msg_lower
        for k in (
            "ciao", "salve", "buongiorno", "buonasera", "hey", "piacere",
            "conoscerti", "presento", "sono ", "mi chiamo",
        )
    )
    is_factual = any(
        k in msg_lower
        for k in (
            "quando sei nato", "quando nacque", "data di nascita", "anno di nascita",
            "dove sei nato", "dove nacque", "quanti anni", "che anno", "sei nato",
            "è nato", "nascita", "insegn", "cattedra",
        )
    )
    banned = (
        "VIETATO in questa risposta: «Ah, ma che volete?», «Capite?», domande retoriche finali, "
        "secondo paragrafo dopo aver già risposto, digressioni su maschere/date/nomi se non richieste."
    )
    if is_factual:
        brevity = (
            "REGOLA: domanda biografica o di fatto. Rispondi in 1 frase (2 al massimo) con il dato richiesto. "
            "Niente Mattia Pascal, metamorfosi, opere, prediche. " + banned
        )
        stream_temp = 0.45
    elif is_light:
        brevity = (
            "REGOLA: saluto o presentazione. 1-2 frasi calde; usa il nome se te lo danno. "
            + banned
        )
        stream_temp = 0.5
    elif any(
        k in msg_lower
        for k in (
            "a piacere", "a caso", "argomento a", "scegli tu", "quello che vuoi",
            "di tua scelta", "a tua scelta",
        )
    ):
        brevity = (
            "REGOLA: richiesta aperta. Scegli un tema pirandelliano e rispondi in 2-4 frasi. "
            "VIETATO iniziare ripetendo o parafrasando la domanda («Parlami di…», «Ora parliamo di…»). "
            "Entra direttamente nel discorso. " + banned
        )
        stream_temp = 0.55
    else:
        brevity = (
            "REGOLA: massimo 2-3 frasi; solo domande profonde su opere/temi → fino a 4 frasi, poi stop. "
            "NON iniziare ripetendo la domanda dell'utente. "
            "Risposta completa = fine, senza coda filosofica. " + banned
        )
        stream_temp = 0.55
    conciseness_reminder = {"role": "system", "content": brevity}
    messages.append(conciseness_reminder)
    messages.append(user_msg)

    for _ in range(MAX_MEMORY_TOOL_ITERS):
        response = await chat_once(messages, temperature=0.3, tools=MEMORY_TOOL_DEFINITIONS, provider_name=provider)
        if not response.get("tool_calls"):
            break

        messages.append(response)
        for tc in response["tool_calls"]:
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = {}
            result_str = await execute_memory_tool(tc["function"]["name"], func_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_str,
            })

    async for chunk in stream_chat(messages, temperature=stream_temp, provider_name=provider):
        if chunk["type"] == "token":
            yield chunk
