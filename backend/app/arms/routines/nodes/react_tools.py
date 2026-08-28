"""Bounded ReAct loop over Skills ARM tools. Degrades if MCP/LLM fail."""

from __future__ import annotations

from typing import Any

from app.arms.routines.llm import LLMConfigError, content_to_text, get_chat_model

_MAX_ITERS = 4
_SYSTEM = (
    "You are A.K.I.R.A. Use tools when they help. "
    "Prefer graph tools for stored knowledge and web_search for current facts. "
    "Stop when you can answer."
)


async def react_tools(state: dict[str, Any]) -> dict[str, Any]:
    query = state.get("query") or ""
    try:
        from app.arms.skills import get_tools

        tools = await get_tools()
    except Exception:
        return {"tool_results": []}

    if not tools:
        return {"tool_results": []}

    try:
        model = get_chat_model(temperature=0.0)
        bound = model.bind_tools(tools)
    except LLMConfigError:
        return {"tool_results": []}
    except Exception:
        return {"tool_results": []}

    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

    messages: list[Any] = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=query),
    ]
    results: list[dict[str, Any]] = []
    by_name = {getattr(t, "name", ""): t for t in tools}

    try:
        for _ in range(_MAX_ITERS):
            response = await bound.ainvoke(messages)
            messages.append(response)
            tool_calls = list(getattr(response, "tool_calls", None) or [])
            if not tool_calls:
                text = content_to_text(getattr(response, "content", ""))
                if text:
                    results.append({"type": "final", "content": text})
                break
            for call in tool_calls:
                name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
                args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
                call_id = (
                    call.get("id")
                    if isinstance(call, dict)
                    else getattr(call, "id", "")
                ) or name
                tool = by_name.get(name)
                if tool is None:
                    output = f"unknown tool: {name}"
                else:
                    try:
                        if hasattr(tool, "ainvoke"):
                            output = await tool.ainvoke(args or {})
                        else:
                            output = tool.invoke(args or {})
                    except Exception as exc:
                        output = f"tool error: {exc}"
                results.append({"name": name, "output": output})
                messages.append(
                    ToolMessage(content=str(output), tool_call_id=str(call_id))
                )
    except Exception as exc:
        results.append({"type": "error", "content": str(exc)})

    return {"tool_results": results}
