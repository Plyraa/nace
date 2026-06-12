import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from config import CACHE_DIR, OPENROUTER_BASE_URL, OPENROUTER_MODEL, OPENROUTER_TEMPERATURE


class MissingLLMCache(RuntimeError):
    pass


def _cache_key(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_json(text: str) -> Any:
    value = text.strip()
    if value.startswith("```"):
        value = value.strip("`")
        if value.startswith("json"):
            value = value[4:]
    start_obj = value.find("{")
    start_arr = value.find("[")
    starts = [i for i in (start_obj, start_arr) if i >= 0]
    if starts:
        value = value[min(starts) :]
    end_obj = value.rfind("}")
    end_arr = value.rfind("]")
    end = max(end_obj, end_arr)
    if end >= 0:
        value = value[: end + 1]
    return json.loads(value)


def _repair_json(client: OpenAI, broken: str, request: dict[str, Any]) -> Any:
    response = client.chat.completions.create(
        model=request["model"],
        temperature=0,
        max_tokens=request["max_tokens"],
        messages=[
            {"role": "system", "content": "Bozuk JSON'u geçerli JSON'a çevir. Sadece JSON döndür."},
            {"role": "user", "content": broken[:6000]},
        ],
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or "{}"


def call_json(
    *,
    task: str,
    system: str,
    user: str,
    model: str = OPENROUTER_MODEL,
    temperature: float = OPENROUTER_TEMPERATURE,
    max_tokens: int = 800,
    retries: int = 3,
) -> Any:
    CACHE_DIR.mkdir(exist_ok=True)
    request = {
        "task": task,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    key = _cache_key(request)
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached["parsed"]

    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise MissingLLMCache(f"No cached response for {task}:{key} and OPENROUTER_API_KEY is not set")

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key, timeout=60)
    last_error = None
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=request["messages"],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            try:
                parsed = _extract_json(content)
            except json.JSONDecodeError:
                content = _repair_json(client, content, request)
                parsed = _extract_json(content)
            path.write_text(
                json.dumps(
                    {"request": request, "raw_response": content, "parsed": parsed},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return parsed
        except Exception as exc:  # network/provider failures are retried uniformly
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"LLM call failed for {task}: {last_error}") from last_error
