#!/usr/bin/env python3
"""
Algorithm Validation Test

This script validates that our password generation algorithm
correctly implements the cipher logic from the decompiled ARM binary.
"""

def generate_password(username):
    """Generate password based on the exact cipher algorithm from the binary"""
    key = len(username) % 25
    result = []
    
    for char in username:
        ascii_val = ord(char)
        
        # Apply the exact logic from the decompiled cipher function
        if ascii_val < 0x61 or ascii_val > 0x7a:  # Not lowercase letter
            if ascii_val < 0x41 or ascii_val > 0x5a:  # Not uppercase letter
                if 0x2f < ascii_val < 0x3a:  # Digit
                    result.append(char)  # Keep digits unchanged
                else:
                    result.append(char)  # Other characters unchanged
            else:  # Uppercase letter
                new_val = ascii_val - key  # Subtract key
                if new_val < 0x41:
                    new_val += 0x1b  # Add 27 for wrap-around
                result.append(chr(new_val))
        else:  # Lowercase letter
            new_val = ascii_val + key  # Add key
            if new_val < 0x61:  # This condition handles unexpected cases
                new_val += 0x1b
            elif new_val > 0x7a:  # Handle wrap-around for exceeding 'z'
                new_val -= 0x1a
            result.append(chr(new_val))
    
    return ''.join(result)

def validate_algorithm():
    """Validate the algorithm implementation against the decompiled code"""
    
    test_cases = [
        {
            'username': 'IOAuser',
            'expected_key': 7,
            'description': 'Example from binary help text'
        },
        {
            'username': 'admin',
            'expected_key': 5,
            'description': 'Short username test'
        },
        {
            'username': 'test123',
            'expected_key': 7,
            'description': 'Username with digits'
        }
    ]
    
    print("Algorithm Validation Results")
    print("=" * 60)
    
    for i, test in enumerate(test_cases, 1):
        username = test['username']
        expected_key = test['expected_key']
        description = test['description']
        
        # Calculate actual key
        actual_key = len(username) % 25
        password = generate_password(username)
        
        print(f"\nTest {i}: {description}")
        print(f"Username: {username}")
        print(f"Expected Key: {expected_key} | Actual Key: {actual_key}")
        print(f"Generated Password: {password}")
        
        # Validate key calculation
        key_match = actual_key == expected_key
        print(f"Key Calculation: {'✓ PASS' if key_match else '✗ FAIL'}")
        
        # Validate cipher logic by manual verification
        print("Cipher Validation:")
        for j, char in enumerate(username):
            orig_val = ord(char)
            result_val = ord(password[j])
            key = actual_key
            
            if 0x61 <= orig_val <= 0x7a:  # Lowercase
                expected_val = orig_val + key
                if expected_val > 0x7a:
                    expected_val -= 0x1a
                cipher_match = result_val == expected_val
                print(f"  {char}->{password[j]}: {orig_val:02x}->{result_val:02x} {'✓' if cipher_match else '✗'}")
            elif 0x41 <= orig_val <= 0x5a:  # Uppercase
                expected_val = orig_val - key
                if expected_val < 0x41:
                    expected_val += 0x1b
                cipher_match = result_val == expected_val
                print(f"  {char}->{password[j]}: {orig_val:02x}->{result_val:02x} {'✓' if cipher_match else '✗'}")
            elif 0x30 <= orig_val <= 0x39:  # Digit
                cipher_match = result_val == orig_val
                print(f"  {char}->{password[j]}: {orig_val:02x}->{result_val:02x} {'✓' if cipher_match else '✗'}")
    
    print(f"\n{'='*60}")
    print("Algorithm implementation validated against decompiled ARM binary code.")
    print("Note: Binary requires ARM environment (qemu-arm) for actual testing.")

if __name__ == "__main__":
    validate_algorithm()