import secrets
import string
import os

def generate_token(length=32):
    """Generates a secure random token."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

def main():
    token = generate_token()
    filename = "admin_token.txt"

    # Write to file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(token)

    print("="*60)
    print("LYRN ADMIN TOKEN GENERATED")
    print("="*60)
    print(f"\nA new admin token has been generated and saved to '{filename}'.")
    print(f"\nTOKEN: {token}")
    print("\nINSTRUCTIONS:")
    print("1. This file ('admin_token.txt') must remain in the root directory")
    print("   for the server to authenticate requests.")
    print("2. To access the Model Manager features, you can either:")
    print("   a) Copy the text above and paste it into the manual entry field.")
    print("   b) Transfer this 'admin_token.txt' file to your client device")
    print("      and use the 'Upload Token File' button in the interface.")
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
