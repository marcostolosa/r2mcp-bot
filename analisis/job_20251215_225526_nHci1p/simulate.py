#!/usr/bin/env python3
"""
Let me trace through the exact logic from the disassembly:

1. scanf("%d", &var_14h) - read integer
2. eax = var_14h
3. cvtsi2ss xmm0, eax (convert int to float)
4. addss xmm0, [0x000008b4] (add 3.56399989)
5. cvttss2si eax, xmm0 (convert float back to int, truncating)
6. var_10h = eax
7. var_8h = 0.0
8. jmp to loop start

Loop:
- cvtsi2ss xmm0, var_10h (convert current int to float)
- ucomiss xmm0, var_8h (compare)
- ja 0x76f (if var_10h > var_8h, continue loop)

At 0x76f (loop body):
- cvtsi2ss xmm0, var_10h
- addss xmm0, var_8h
- movss xmm1, var_4h  
- addss xmm0, xmm1
- movss var_4h, xmm0 (accumulating result in var_4h)
- movss xmm1, var_8h
- addss xmm0, [0x000008b8] (add 0.800000012)
- addss xmm0, xmm1  
- movss var_8h, xmm0 (increment counter by 0.800000012)

After loop:
- cvtss2sd xmm0, var_4h
- printf("%f", result)
- ucomiss var_4h, [0x000008bc] (compare with 4550.7998)
- jp/jne -> "Bad password"
- -> "Good password"
"""

def simulate_algorithm(input_int):
    CONST1 = 3.56399989
    CONST2 = 0.800000012  
    TARGET = 4550.7998
    
    print(f"Input: {input_int}")
    
    # Step 1-6: Initial processing
    step1_float = float(input_int)
    print(f"  As float: {step1_float}")
    
    step2_float = step1_float + CONST1
    print(f"  + CONST1: {step2_float}")
    
    var_10h = int(step2_float)  # truncates
    print(f"  Truncated to int: {var_10h}")
    
    # Initialize loop variables
    var_8h = 0.0  # loop counter
    var_4h = 0.0  # accumulator
    
    print(f"  Loop: var_10h={var_10h}, var_8h starts at {var_8h}")
    
    # Simulate the loop
    iteration = 0
    while var_10h > var_8h:
        # Loop body
        temp = float(var_10h) + var_8h + var_4h
        var_4h = temp
        
        var_8h = var_8h + CONST2
        iteration += 1
        
        if iteration < 5 or iteration % 1000 == 0:
            print(f"    Iter {iteration}: var_4h={var_4h}, var_8h={var_8h}")
        
        if iteration > 10000:  # safety
            print("    Too many iterations, breaking")
            break
    
    print(f"  Final: var_4h={var_4h}, var_8h={var_8h}")
    print(f"  Iterations: {iteration}")
    print(f"  Compare var_4h ({var_4h}) with TARGET ({TARGET})")
    print(f"  Result: {'Good password' if abs(var_4h - TARGET) < 0.001 else 'Bad password'}")
    print()
    
    return abs(var_4h - TARGET) < 0.001

def find_solution():
    print("Searching for solution...")
    for test_input in range(-1000, 1001):
        if simulate_algorithm(test_input):
            print(f"SOLUTION FOUND: {test_input}")
            return test_input
    
    print("No solution found in range -1000 to 1000")
    return None

if __name__ == "__main__":
    # Test with some inputs
    for test in [0, 1, 10, 100]:
        print("=" * 50)
        simulate_algorithm(test)
    
    print("=" * 50)
    print("Searching for solution...")
    solution = find_solution()