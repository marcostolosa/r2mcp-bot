#!/usr/bin/env python3
"""
Keygen for the input.bin crackme

This script generates the correct password by reverse engineering the mathematical
algorithm used in the binary.
"""

def solve_crackme():
    """
    Solve the crackme by working backwards from the target value.
    """
    # Constants extracted from the binary
    CONST1 = 3.56399989      # Added to input before truncation
    CONST2 = 0.800000012      # Increment in each loop iteration  
    TARGET = 4550.7998        # Target value to match
    
    # The algorithm:
    # 1. var_10h = int(input + CONST1)
    # 2. Loop: var_4h += var_10h + var_8h; var_8h += CONST2
    # 3. Stop when var_10h <= var_8h
    # 4. Check if var_4h == TARGET
    
    # Working backwards mathematically:
    # The loop formula is: var_4h = n * var_10h + CONST2 * n * (n-1) / 2
    # where n ≈ var_10h / CONST2 when the loop stops
    
    # Substituting and solving the quadratic equation:
    # 3 * var_10h^2 - var_10h * CONST2 - 2 * TARGET * CONST2 = 0
    
    a = 3.0
    b = -CONST2
    c = -2.0 * TARGET * CONST2
    
    discriminant = b*b - 4*a*c
    sqrt_disc = discriminant ** 0.5
    
    # Take the positive root
    var_10h = int((-b + sqrt_disc) / (2*a))
    
    # Work backwards to get the original input
    original_input = var_10h - CONST1
    
    # Try both floor and ceil due to truncation in original
    candidates = [int(original_input), int(original_input) + 1]
    
    for candidate in candidates:
        if verify_simulation(candidate):
            return candidate
    
    return int(round(original_input))

def verify_simulation(password):
    """
    Quick simulation check without verbose output
    """
    CONST1 = 3.56399989
    CONST2 = 0.800000012
    TARGET = 4550.7998
    
    step2_float = float(password) + CONST1
    var_10h = int(step2_float)
    
    var_8h = 0.0
    var_4h = 0.0
    
    while var_10h > var_8h:
        var_4h = var_4h + var_10h + var_8h
        var_8h = var_8h + CONST2
    
    return abs(var_4h - TARGET) < 0.001

def verify_solution(password):
    """
    Verify that the password works by simulating the algorithm.
    """
    CONST1 = 3.56399989
    CONST2 = 0.800000012
    TARGET = 4550.7998
    
    # Simulate the algorithm
    step2_float = float(password) + CONST1
    var_10h = int(step2_float)
    
    var_8h = 0.0
    var_4h = 0.0
    iteration = 0
    
    while var_10h > var_8h:
        var_4h = var_4h + var_10h + var_8h
        var_8h = var_8h + CONST2
        iteration += 1
        
        if iteration > 100000:  # safety
            break
    
    success = abs(var_4h - TARGET) < 0.001
    
    print(f"Input: {password}")
    print(f"var_10h: {var_10h}")
    print(f"Iterations: {iteration}")
    print(f"Final result: {var_4h}")
    print(f"Target: {TARGET}")
    print(f"Result: {'✓ Good password' if success else '✗ Bad password'}")
    
    return success

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Keygen for input.bin crackme')
    parser.add_argument('-v', '--verify', action='store_true', 
                       help='Verify the solution by simulating the algorithm')
    parser.add_argument('-p', '--password', type=int,
                       help='Test a specific password')
    
    args = parser.parse_args()
    
    if args.password is not None:
        # Test specific password
        verify_solution(args.password)
    else:
        # Generate the correct password
        solution = solve_crackme()
        print(f"The correct password is: {solution}")
        
        if args.verify:
            print()
            verify_solution(solution)

if __name__ == "__main__":
    main()