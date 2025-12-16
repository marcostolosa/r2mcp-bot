#!/usr/bin/env python3
"""
Password Generator for ARM Crackme

This script implements the password generation algorithm discovered in the ARM crackme binary.
Given a username, it calculates the corresponding password that would pass the authentication.
"""

def generate_password(username):
    """
    Generate the password for the given username based on the cipher algorithm.
    
    Args:
        username (str): The input username
        
    Returns:
        str: The calculated password that would pass the crackme
    """
    # Calculate key: username length % 25 (0x19 in hex)
    key = len(username) % 25
    
    password_chars = []
    
    for char in username:
        ascii_val = ord(char)
        
        # Handle different character types based on the cipher logic
        if ascii_val < 0x61 or ascii_val > 0x7a:  # Not lowercase letter
            if ascii_val < 0x41 or ascii_val > 0x5a:  # Not uppercase letter
                if 0x2f < ascii_val < 0x3a:  # Digit (0x30-0x39)
                    # Digits remain unchanged
                    password_chars.append(char)
                else:
                    # Other characters remain unchanged (not explicitly handled in cipher)
                    password_chars.append(char)
            else:  # Uppercase letter (A-Z)
                # Shift backward by key positions
                new_ascii = ascii_val - key
                if new_ascii < 0x41:  # If before 'A', wrap around
                    new_ascii += 0x1b  # Add 27 (0x1b)
                password_chars.append(chr(new_ascii))
        else:  # Lowercase letter (a-z)
            # Shift forward by key positions
            new_ascii = ascii_val + key
            if new_ascii < 0x61:  # This condition seems incorrect in original, should be > 'z'
                # Based on the cipher logic, this should handle wrap-around
                new_ascii += 0x1b  # Add 27 (0x1b)
            # Handle wrap-around for exceeding 'z'
            elif new_ascii > 0x7a:
                new_ascii -= 0x1a  # Subtract 26 to wrap around
            password_chars.append(chr(new_ascii))
    
    return ''.join(password_chars)

def main():
    """
    Main function to demonstrate password generation.
    """
    import sys
    
    print("ARM Crackme Password Generator")
    print("=" * 40)
    
    # Check if username provided as command line argument
    if len(sys.argv) > 1:
        username = sys.argv[1]
        password = generate_password(username)
        key = len(username) % 25
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"Key: {key}")
        print(f"Usage: ./input.bin {username} {password}")
        return
    
    # Demo mode with predefined examples
    test_usernames = [
        "IOAuser",
        "admin", 
        "test123",
        "crackme"
    ]
    
    print("\nExample password generations:")
    for username in test_usernames:
        password = generate_password(username)
        key = len(username) % 25
        print(f"Username: {username:<10} | Key: {key:<2} | Password: {password}")
    
    print(f"\nTo generate password for a specific username:")
    print(f"python3 {sys.argv[0]} <username>")

if __name__ == "__main__":
    main()