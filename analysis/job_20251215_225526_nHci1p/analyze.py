#!/usr/bin/env python3
"""
Reverse engineered algorithm for the crackme

Based on disassembly analysis:
- Reads an integer using scanf("%d")
- Converts to float and adds constant 3.56399989
- Converts back to integer
- Then runs a loop that appears to accumulate values
- Final check compares result against 4550.7998

Let me trace through the logic:
"""

def analyze_algorithm():
    # Constants from the binary
    CONST1 = 3.56399989  # at 0x000008b4
    CONST2 = 0.800000012  # at 0x000008b8  
    TARGET = 4550.7998  # at 0x000008bc
    
    print(f"Constants found:")
    print(f"  CONST1 = {CONST1}")
    print(f"  CONST2 = {CONST2}")
    print(f"  TARGET = {TARGET}")
    print()
    
    # From analysis:
    # 1. Read integer input
    # 2. Convert to float, add CONST1, convert back to int
    # 3. Then some accumulation loop that increases by CONST2 each iteration
    # 4. Final result should equal TARGET
    
    # Let's work backwards
    # If final result should be TARGET, and we add CONST2 in a loop...
    # Let me try to understand the loop better
    
    print("Working backwards from TARGET:")
    # The loop seems to increment by CONST2 each time
    # So we need to find how many iterations: TARGET / CONST2
    iterations = TARGET / CONST2
    print(f"Estimated iterations: {iterations}")
    
    # The value starts as the converted integer, then accumulates
    # So initial_value + (iterations * CONST2) = TARGET
    # initial_value = TARGET - (iterations * CONST2)
    
    # But iterations might be an integer...
    for i in range(int(iterations) - 10, int(iterations) + 10):
        if i > 0:
            initial_val = TARGET - (i * CONST2)
            print(f"  If {i} iterations: initial value = {initial_val}")
            
            # This initial value came from converting: int(input + CONST1)
            # So input + CONST1 ≈ initial_val
            input_val = initial_val - CONST1
            print(f"    Input would be: {input_val}")

if __name__ == "__main__":
    analyze_algorithm()