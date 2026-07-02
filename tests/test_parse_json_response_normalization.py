from schemas import TopicSuggestionsResult
import deepseek_client


def test_parse_json_model_strips_think_prefix_from_json_response(monkeypatch):
    payload = '<think>internal reasoning</think>{"suggestions":[{"title":"Topic A","angle":"Angle A","reason":"Reason A","reader_pain_point":"Pain A","material_basis":"Basis A"}]}'
    monkeypatch.setattr(
        deepseek_client,
        "sdk_chat_completion",
        lambda messages, json_mode=False, setting=None: payload,
    )
    monkeypatch.setattr(deepseek_client, "current_setting", lambda setting=None: {"api_key": "test-key"})

    result = deepseek_client.parse_json_model(
        TopicSuggestionsResult,
        [{"role": "user", "content": "generate topics"}],
        setting={"api_key": "test-key"},
    )

    assert result.suggestions[0].title == "Topic A"


def test_normalize_json_response_text_extracts_json_from_fenced_payload():
    payload = "```json\n{\"ok\": true, \"value\": 1}\n```"

    normalized = deepseek_client._normalize_json_response_text(payload)

    assert normalized == '{"ok": true, "value": 1}'
