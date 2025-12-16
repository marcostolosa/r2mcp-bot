# Reverse Engineering Report: Crackme input.bin

## Binary Overview

- **Architecture**: x86_64 ELF
- **Size**: 8.5KB (6711 bytes)
- **Type**: Shared object (DYN)
- **Compiler**: GCC 6.3.0 (Debian)
- **Entry Point**: 0x5f0
- **Main Function**: 0x720

## Initial Analysis

The binary is a simple password checker that:

1. Reads an integer using `scanf("%d")`
2. Performs mathematical transformations
3. Compares the result against a target value
4. Prints "Good password" or "Bad password"

## Strings and Constants

Key constants found in memory:

- `0x000008b4`: 3.56399989 (float)
- `0x000008b8`: 0.800000012 (float) 
- `0x000008bc`: 4550.7998 (float) - **target value**

Strings:

- "Good pasword" (note: typo in original)
- "Bad password"
- "%d" - input format
- "%f" - output format

## Algorithm Analysis

### Step-by-step disassembly analysis:

1. **Input Processing**:

   ```c
   scanf("%d", &input);
   float temp = (float)input + 3.56399989;
   int var_10h = (int)temp;  // truncate
   ```

2. **Loop Initialization**:

   ```c
   float var_8h = 0.0;  // loop counter
   float var_4h = 0.0;  // accumulator
   ```

3. **Main Loop**:

   ```c
   while (var_10h > var_8h) {
       var_4h = var_4h + var_10h + var_8h;
       var_8h = var_8h + 0.800000012;
   }
   ```

4. **Final Check**:
5. 
   ```c
   printf("%f", var_4h);
   if (var_4h == 4550.7998) {
       printf("Good password");
   } else {
       printf("Bad password");
   }
   ```

### Mathematical Formula

The loop creates a triangular number pattern:
- After `n` iterations: `var_8h = n × 0.800000012`
- Accumulator: `var_4h = n × var_10h + 0.800000012 × n × (n-1) ÷ 2`

The loop stops when `var_8h ≈ var_10h`, which happens at `n ≈ var_10h ÷ 0.800000012`.

## Solution Derivation

Working backwards from the target:

1. **Quadratic equation**: `3 × var_10h² - 0.800000012 × var_10h - 2 × 4550.7998 × 0.800000012 = 0`
2. **Solution**: `var_10h ≈ 49.4` (positive root)
3. **Integer value**: `var_10h = 49`
4. **Original input**: `input = var_10h - 3.56399989 ≈ 45.4`
5. **Integer input**: `input = 46`

### Verification:

For input `46`:

- `var_10h = int(46 + 3.56399989) = int(49.56399989) = 49`
- Loop runs 62 iterations (`49 ÷ 0.800000012 ≈ 61.25`)
- Final `var_4h = 4550.800022692001 ≈ 4550.7998` ✓

## Classification

**Type**: Simple password checker with mathematical algorithm

**Difficulty**: Easy-Medium (requires reverse engineering the floating-point algorithm)

**Key insight**: The loop creates a triangular number accumulation pattern

## Solution

The correct password is: **46**

## Files Created

1. `keygen.py` - Standalone Python script to generate the solution
2. This report (`report.md`) - Comprehensive analysis documentation

## Keygen Script

```python
#!/usr/bin/env python3
def solve_crackme():
    CONST1 = 3.56399989
    CONST2 = 0.800000012  
    TARGET = 4550.7998
    
    # Mathematical solution
    a = 3.0
    b = -CONST2
    c = -2.0 * TARGET * CONST2
    
    discriminant = b*b - 4*a*c
    sqrt_disc = discriminant ** 0.5
    var_10h = int((-b + sqrt_disc) / (2*a))
    
    return var_10h - CONST1

if __name__ == "__main__":
    solution = solve_crackme()
    print(f"Password: {int(solution)}")
```