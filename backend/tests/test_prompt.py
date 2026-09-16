from app.extractor.prompt import chunk_instruction, interaction_input


def test_chunk_instructions_differ() -> None:
    zero = chunk_instruction(0)
    one = chunk_instruction(1)
    assert zero != one
    assert "bağlam" in one
    assert "listeleme" in one


def test_interaction_input_has_no_identity() -> None:
    payload = interaction_input("Zg==", 0)
    blob = str(payload)
    assert "dev@local" not in blob
    assert "user_id" not in blob
    assert "password" not in blob.lower()
