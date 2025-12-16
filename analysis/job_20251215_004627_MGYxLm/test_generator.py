#!/usr/bin/env python3
"""
Simple test of the password generation algorithm
"""

def generate_password(username):
    """Generate password for given username based on crackme cipher algorithm"""
    key = len(username) % 25
    
    password_chars = []
    
    for char in username:
        ascii_val = ord(char)
        
        if ascii_val < 0x61 or ascii_val > 0x7a:  # Not lowercase letter
            if ascii_val < 0x41 or ascii_val > 0x5a:  # Not uppercase letter
                if 0x2f < ascii_val < 0x3a:  # Digit
                    password_chars.append(char)
                else:
                    password_chars.append(char)
            else:  # Uppercase letter - shift backward
                new_ascii = ascii_val - key
                if new_ascii < 0x41:
                    new_ascii += 0x1b
                password_chars.append(chr(new_ascii))
        else:  # Lowercase letter - shift forward
            new_ascii = ascii_val + key
            # Handle wrap-around correctly
            while new_ascii > 0x7a:
                new_ascii -= 0x1a
            password_chars.append(chr(new_ascii))
    
    return ''.join(password_chars)

# Test the algorithm
test_cases = [
    "IOAuser",
    "admin",
    "test123",
    "crackme"
]

print("Password Generation Test Results:")
print("=" * 50)

for username in test_cases:
    password = generate_password(username)
    key = len(username) % 25
    print(f"Username: {username:<10} | Key: {key:<2} | Password: {password}")

# Test with example from binary help text
username = "IOAuser"
password = generate_password(username)
print(f"\nExample from binary help:")
print(f"Command: ./input.bin {username} {password}")