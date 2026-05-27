import json
from backend.memory import user_memory as mem

MEMORY_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_user_fact",
            "description": "Salva un fatto rilevante sull'interlocutore (nome, preferenze, progetti) nella memoria a lungo termine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Categoria (es. identita, preferenza, progetto).",
                    },
                    "key": {
                        "type": "string",
                        "description": "Chiave breve univoca (es. nome, colore_preferito).",
                    },
                    "value": {
                        "type": "string",
                        "description": "Informazione da ricordare.",
                    },
                },
                "required": ["category", "key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "Recupera tutti i fatti memorizzati sull'interlocutore.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_user_fact",
            "description": "Elimina un fatto specifico dalla memoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "key": {"type": "string"},
                },
                "required": ["category", "key"],
            },
        },
    },
]


async def execute_memory_tool(name: str, args: dict) -> str:
    if name == "save_user_fact":
        ok = mem.save_fact(
            args.get("category", "generale"),
            args.get("key", "nota"),
            args.get("value", ""),
        )
        return json.dumps({"success": ok}, ensure_ascii=False)
    if name == "get_user_profile":
        facts = mem.get_all_facts()
        return json.dumps({"facts": facts}, ensure_ascii=False)
    if name == "delete_user_fact":
        ok = mem.delete_fact(args.get("category", ""), args.get("key", ""))
        return json.dumps({"success": ok}, ensure_ascii=False)
    return json.dumps({"error": f"Tool sconosciuto: {name}"}, ensure_ascii=False)
