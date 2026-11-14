from app.services.card_generator import generate_password, generate_username


def test_digits_generation_contains_only_digits():
    value = generate_username(10, "digits", "77")
    assert len(value) == 10
    assert value.startswith("77")
    assert value.isdigit()


def test_letters_generation_contains_only_letters():
    value = generate_username(8, "letters")
    assert len(value) == 8
    assert value.isalpha()
    assert value == value.upper()


def test_alphanumeric_generation_has_requested_length():
    value = generate_username(12, "alphanumeric", "NET")
    assert len(value) == 12
    assert value.startswith("NET")
    assert value.isalnum()


def test_password_generation_has_requested_length():
    assert len(generate_password(14)) == 14
