import json
from backend.agent.prompts import SYSTEM_PROMPT_WIKI_LIBRARIAN
from backend.agent.provider_manager import chat_once
from backend.tools.wiki_search import wiki_search
from backend.tools.wiki_read import wiki_read
from backend.tools.wiki_create import wiki_create
from backend.tools.wiki_update import wiki_update
from backend.tools.wiki_list import wiki_list
from backend.tools.source_read import source_read

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "wiki_search",
            "description": "Cerca pagine nella wiki per keyword",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Parole chiave da cercare"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wiki_read",
            "description": "Legge il contenuto di una pagina wiki",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso relativo della pagina (es. pages/entities/mattia-pascal.md)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wiki_create",
            "description": "Crea una nuova pagina wiki",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Nome del file senza estensione (es. nuovo-personaggio)"},
                    "title": {"type": "string", "description": "Titolo della pagina"},
                    "category": {"type": "string", "description": "Categoria: entities, concepts, sources, synthesis, queries"},
                    "content": {"type": "string", "description": "Contenuto in Markdown (body, senza frontmatter)"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tag opzionali"}
                },
                "required": ["path", "title", "category", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wiki_update",
            "description": "Aggiorna una pagina wiki esistente",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso relativo della pagina (es. pages/entities/mattia-pascal.md)"},
                    "content": {"type": "string", "description": "Nuovo contenuto (body Markdown, senza frontmatter)"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wiki_list",
            "description": "Elenca pagine wiki per categoria",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Categoria opzionale (entities, concepts, sources, synthesis, queries)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "source_read",
            "description": "Legge un file sorgente da raw/",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso relativo del file (es. articles/pena-di-vivere-cosi.txt)"}
                },
                "required": ["path"]
            }
        }
    }
]

TOOL_MAP = {
    "wiki_search": wiki_search,
    "wiki_read": wiki_read,
    "wiki_create": wiki_create,
    "wiki_update": wiki_update,
    "wiki_list": wiki_list,
    "source_read": source_read,
}

MAX_AGENT_ITERS = 5

async def wiki_agent_loop(user_message: str, history: list, provider: str = None):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_WIKI_LIBRARIAN},
        *history,
        {"role": "user", "content": user_message},
    ]

    for iteration in range(MAX_AGENT_ITERS):
        response = await chat_once(messages, temperature=0.3, tools=TOOL_DEFINITIONS, provider_name=provider)

        if response.get("tool_calls"):
            messages.append(response)
            for tc in response["tool_calls"]:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}

                tool_fn = TOOL_MAP.get(func_name)
                if tool_fn:
                    try:
                        result = await tool_fn(**func_args)
                        result_str = json.dumps(result, ensure_ascii=False)
                    except Exception as e:
                        result_str = json.dumps({"error": str(e)}, ensure_ascii=False)
                else:
                    result_str = json.dumps({"error": f"Tool sconosciuto: {func_name}"}, ensure_ascii=False)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })
        else:
            content = response.get("content", "") or ""
            if content:
                yield {"type": "token", "content": content}
            return

    yield {"type": "token", "content": "\n\n*[Agent: ho raggiunto il massimo numero di iterazioni. Se serve, puoi darmi un'istruzione più specifica.]*"}
