#!/usr/bin/env python3
"""
Let me search more systematically for the right input.
The key insight is that var_10h needs to be positive and large enough to make the loop run enough times.
"""

def find_solution_wider():
    CONST1 = 3.56399989
    CONST2 = 0.800000012
    TARGET = 4550.7998
    
    # Try a wider range of positive inputs
    for test_input in range(0, 10000):
        # Process the input
        step2_float = float(test_input) + CONST1
        var_10h = int(step2_float)
        
        # Only proceed if var_10h is positive
        if var_10h > 0:
            # Simulate the loop
            var_8h = 0.0
            var_4h = 0.0
            
            iteration = 0
            while var_10h > var_8h:
                temp = float(var_10h) + var_8h + var_4h
                var_4h = temp
                var_8h = var_8h + CONST2
                iteration += 1
                
                if iteration > 100000:  # safety
                    break
            
            # Check if we got the target
            if abs(var_4h - TARGET) < 0.001:
                print(f"SOLUTION FOUND: {test_input}")
                print(f"  var_10h: {var_10h}")
                print(f"  iterations: {iteration}")
                print(f"  final result: {var_4h}")
                return test_input
    
    print("No solution found in range 0-9999")
    return None

def find_solution_mathematical():
    """
    Let me work backwards mathematically.
    """
    CONST1 = 3.56399989
    CONST2 = 0.800000012
    TARGET = 4550.7998
    
    print("Mathematical analysis:")
    print(f"TARGET = {TARGET}")
    print(f"CONST2 = {CONST2}")
    
    # The loop formula seems to be:
    # var_4h_n+1 = var_4h_n + var_10h + var_8h_n
    # var_8h_n+1 = var_8h_n + CONST2
    # where var_8h_0 = 0, var_4h_0 = 0, and n goes from 0 to var_10h/CONST2 - 1
    
    # This creates a triangular number pattern
    # After n iterations:
    # var_8h = n * CONST2
    # var_4h = sum_{i=0}^{n-1} (var_10h + i * CONST2)
    # var_4h = n * var_10h + CONST2 * sum_{i=0}^{n-1} i
    # var_4h = n * var_10h + CONST2 * n*(n-1)/2
    
    # We need: var_4h ≈ TARGET when var_8h ≈ var_10h
    # This happens when: n * CONST2 ≈ var_10h, so n ≈ var_10h/CONST2
    
    # Plugging n ≈ var_10h/CONST2 into var_4h:
    # var_4h ≈ (var_10h/CONST2) * var_10h + CONST2 * (var_10h/CONST2) * (var_10h/CONST2 - 1) / 2
    # var_4h ≈ var_10h^2/CONST2 + (var_10h^2/CONST2^2 - var_10h/CONST2) * CONST2 / 2
    # var_4h ≈ var_10h^2/CONST2 + (var_10h^2/CONST2 - var_10h) / 2
    # var_4h ≈ (3/2) * var_10h^2/CONST2 - var_10h/2
    
    # So: TARGET ≈ (3/2) * var_10h^2/CONST2 - var_10h/2
    # TARGET ≈ var_10h * (1.5 * var_10h/CONST2 - 0.5)
    
    # Let's solve for var_10h:
    # (3/2) * var_10h^2/CONST2 - var_10h/2 - TARGET = 0
    # 3 * var_10h^2/CONST2 - var_10h - 2*TARGET = 0
    # 3 * var_10h^2 - var_10h*CONST2 - 2*TARGET*CONST2 = 0
    
    a = 3.0
    b = -CONST2
    c = -2.0 * TARGET * CONST2
    
    discriminant = b*b - 4*a*c
    if discriminant >= 0:
        sqrt_disc = discriminant ** 0.5
        var_10h1 = (-b + sqrt_disc) / (2*a)
        var_10h2 = (-b - sqrt_disc) / (2*a)
        
        print(f"Quadratic solutions: var_10h ≈ {var_10h1} or {var_10h2}")
        
        # Try integer values around these solutions
        for var_10h_candidate in [int(var_10h1), int(var_10h1)+1, int(var_10h1)-1]:
            if var_10h_candidate > 0:
                n = int(var_10h_candidate / CONST2)
                var_4h = n * var_10h_candidate + CONST2 * n * (n-1) / 2
                print(f"  var_10h={var_10h_candidate}, n={n}, var_4h={var_4h}")
                
                if abs(var_4h - TARGET) < 1.0:
                    # Now work backwards to find the original input
                    # var_10h = int(input + CONST1)
                    original_input = var_10h_candidate - CONST1
                    print(f"  Original input would be: {original_input}")
    
if __name__ == "__main__":
    find_solution_mathematical()
    print()
    find_solution_wider()