import re


class UserRegistrationError(ValueError):
    pass


USERS = {
    "alice": "alice@example.com",
}


def register_user(username, email, password):
    if not username or len(username) < 3:
        raise UserRegistrationError("Invalid username")

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise UserRegistrationError("Invalid email")

    if username in USERS:
        raise UserRegistrationError("Username already exists")

    if not password:
        raise UserRegistrationError("Password is required")

    if len(password) < 8:
        raise UserRegistrationError("Password too short")

    USERS[username] = email

    return {
        "username": username,
        "email": email,
    }