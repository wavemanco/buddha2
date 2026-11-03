def _editor_request(role: str, request: Any, tools: dict) -> None:
    required = {"model": "claude-opus-5", "max_tokens": 16000, "thinking": {"type": "adaptive"},
                "output_config": {"effort": "high"}, "service_tier": "standard_only", "inference_geo": "global"}
    controls = copy.deepcopy(request) if isinstance(request, dict) else {}
    config = controls.get("output_config")
    if role == "fixed_selector" and isinstance(config, dict) and "format" in config:
        formatting = config["format"]
        _require(isinstance(formatting, dict) and set(formatting) == {"type", "schema"}
                 and formatting["type"] == "json_schema" and isinstance(formatting["schema"], dict),
                 "unsupported fixed selector structured schema")
        controls["output_config"] = {k: v for k, v in config.items() if k != "format"}
    _require(isinstance(request, dict) and set(request).issubset(set(required) | {
        "messages", "system", "tools", "tool_choice", "stream", "metadata"}) and
        all(type(controls.get(k)) is type(v) and controls.get(k) == v for k, v in required.items()),
        "editor/selector changed a frozen model/profile or added unsupported fields")
    _require("stream" not in request or type(request["stream"]) is bool, "invalid streaming control")
    if "metadata" in request:
        metadata = request["metadata"]
        _require(isinstance(metadata, dict) and set(metadata) == {"user_id"}
                 and isinstance(metadata["user_id"], str) and len(metadata["user_id"]) <= 256,
                 "unsupported editor request metadata")
    _require("system" not in request or _text(request["system"]), "unsupported editor system content")
    supplied = request.get("tools", [])
    _require(isinstance(supplied, list) and len(supplied) == len({t.get("name") for t in supplied if isinstance(t, dict)})
             and all(isinstance(t, dict) and t.get("name") in tools and t == tools[t["name"]] for t in supplied),
             "editor tool definitions differ from the frozen allowed client tools")
    names = {tool["name"] for tool in supplied}
    _require("tool_choice" not in request or request["tool_choice"] in ({"type": "auto"}, {"type": "none"}),
             "unsupported editor tool selection")
    messages = request.get("messages")
    _require(isinstance(messages, list) and messages, "editor requires explicit messages")
    tool_ids: set[str] = set()
    for message in messages:
        _require(isinstance(message, dict) and set(message) == {"role", "content"}
                 and message["role"] in {"user", "assistant"}, "unsupported editor message envelope")
        content = message["content"]
        if _text(content):
            continue
        _require(role == "editor" and isinstance(content, list), "selector supports only text, without tools")
        for block in content:
            _require(isinstance(block, dict), "invalid editor content block")
            kind = block.get("type")
            cache_keys = {"cache_control"} if "cache_control" in block else set()
            if cache_keys:
                _require(_cache_control(block["cache_control"]), "unsupported editor continuation cache policy")
            if kind == "text":
                _require(_text([block]), "invalid editor text block")
            elif kind == "tool_use":
                caller_keys = {"caller"} if "caller" in block else set()
                _require(not caller_keys or block["caller"] == {"type": "direct"},
                         "only direct client-tool caller metadata is supported")
                _require(set(block) == {"type", "id", "name", "input"} | cache_keys | caller_keys and block["name"] in names
                         and isinstance(block["id"], str) and block["id"] not in tool_ids and
                         message["role"] == "assistant" and isinstance(block["input"], dict), "invalid client tool call")
                tool_ids.add(block["id"])
            elif kind == "tool_result":
                _require(set(block).issubset({"type", "tool_use_id", "content", "is_error"} | cache_keys)
                         and block.get("tool_use_id") in tool_ids and message["role"] == "user" and _text(block.get("content"))
                         and ("is_error" not in block or type(block["is_error"]) is bool), "invalid client tool result")
            elif kind == "thinking":
                _require(set(block) == {"type", "thinking", "signature"} and
                         isinstance(block["thinking"], str) and isinstance(block["signature"], str), "invalid thinking continuation")
            elif kind == "redacted_thinking":
                _require(set(block) == {"type", "data"} and isinstance(block["data"], str), "invalid redacted continuation")
            else:
                raise ContractError("unsupported editor content or server tool")
    _require(role != "fixed_selector" or not supplied and "tool_choice" not in request, "fixed selector cannot use tools")
    _require(len(_wire(request)) <= POLICY["editor_payload_bytes"], "editor/selector exact request exceeds payload limit")
