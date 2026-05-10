from getpass import getpass

from app.core.security import hash_password


def main():
    password = getpass("New admin password: ")
    confirm = getpass("Confirm admin password: ")

    if password != confirm:
        raise SystemExit("Passwords do not match.")

    if len(password) < 14:
        raise SystemExit("Use at least 14 characters.")

    print(hash_password(password))


if __name__ == "__main__":
    main()
