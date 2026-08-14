from open_coding_agent.memory import load_system_prompt


def test_load_system_prompt_returns_nonempty_text():
    prompt = load_system_prompt()

    assert "OpenCodingAgent" in prompt
    assert len(prompt) > 0


def test_load_system_prompt_mentions_the_tools_it_guides():
    prompt = load_system_prompt()

    assert "search_files" in prompt
    assert "edit_file" in prompt
