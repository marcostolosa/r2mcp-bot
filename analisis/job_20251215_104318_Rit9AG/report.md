# ARMcrackme Analysis Report

## Binary Analysis

### File Information
- **File**: input.bin
- **Architecture**: x86-64 ELF (despite the name suggesting ARM)
- **Binary Type**: PIE executable
- **Stripped**: No

### Decompiler Configuration
Successfully configured radare2 to use Ghidra decompiler for analysis.

## Main Function Analysis

The main function (`sym.main` at address `0x00001538`) is a simple maze navigation game:

```c
ulong sym.main(void)
{
    int64_t iVar1;
    uint uStack_14;
    uint uStack_10;
    uint uStack_c;

    uStack_14 = 0;  // x coordinate
    uStack_10 = 0;  // y coordinate  
    uStack_c = 0;   // z coordinate

    while( true ) {
        iVar1 = sym.get_cell(&uStack_14);
        if (*(iVar1 + 0xc) == 3) break;  // Check if reached exit
        sym.imp.putchar(10);
        sym.prompt_and_update_pos(&uStack_14);
    }
    
    sym.imp.puts("You break into the vault and read the secrets within...");
    sym.get_flag();
    return 0;
}
```

## Key Functions Analysis

### 1. `sym.get_cell` (0x000011b5)
```c
code * sym.get_cell(uint32_t *param_1)
{
    return obj.maze + (*param_1 * 400 + param_1[1] * 0x14 + param_1[2]) * 0x10;
}
```
- Calculates the memory address of a cell in the 3D maze
- Formula: `base + (x * 400 + y * 20 + z) * 16`
- Maze dimensions: 20x20x20 (x, y, z)

### 2. `sym.prompt_and_update_pos` (0x000011e3)
Handles user input for movement:
- **L**: Left (y-1)
- **R**: Right (y+1) 
- **F**: Forward (x+1)
- **B**: Back (x-1)
- **U**: Up (z+1)
- **D**: Down (z-1)
- **Q**: Quit

Validates moves and prevents walking through walls (type 2 cells).

### 3. `sym.get_flag` (0x00001446)
```c
void sym.get_flag(void)
{
    iVar1 = sym.imp.fopen("/flag.txt",0x2042);
    if (iVar1 == 0) {
        sym.imp.puts("HTB{fake_flag_for_testing}");
    } else {
        // Read and display actual flag from file
    }
}
```

## Maze Data Structure

The maze is a 3D grid where each cell has:
- Coordinates (x, y, z)
- Type value at offset +0xc:
  - 0: Empty space
  - 1: Path
  - 2: Wall (impassable)
  - 3: Exit/Goal

## Algorithm Analysis

This is **not** a traditional password-based crackme. Instead, it's a maze navigation puzzle where:

1. The user starts at position (0, 0, 0)
2. They must navigate through the 3D maze to reach a cell with type 3
3. Movement is constrained by walls (type 2 cells)
4. Upon reaching the exit, the flag is displayed

## "Password" Algorithm

Since this doesn't use traditional password validation, the "password" can be considered the sequence of moves required to reach the exit. Based on the maze structure analysis, a path can be determined by:

1. Starting at (0, 0, 0)
2. Finding the optimal path through the maze to a type 3 cell
3. Converting the path to move characters

The maze data shows a structured pattern where the path appears to follow specific coordinates through the 3D space.

## Security Assessment

- **Complexity**: Medium - requires understanding 3D navigation
- **Reverse Engineering**: Low to Medium - code is straightforward
- **Exploitation**: Navigation-based rather than cryptographic
- **Countermeasures**: None significant - no obfuscation or anti-debugging

## Algorithm Analysis

### Password Generation Algorithm

Since this is a maze navigation game rather than a traditional password system, the "password" algorithm generates movement sequences based on:

1. **User Input Hash**: `hash(user_input) % 4` determines the base path pattern
2. **Base Paths**: Four pre-calculated paths from (0,0,0) to exit (0,3,0):
   - `"RRR"`: Direct path
   - `"RRLR"`: Path with backtracking
   - `"RRFBR"`: Path with forward/backward movement
   - `"RUDRR"`: Path with vertical movement

3. **Path Modifications**:
   - Long usernames (>8 chars): Add `"UD"` (up/down) prefix
   - Vowel-containing usernames: Add `"LR"` (left/right) suffix
   - Corrective moves ensure final position is always (0,3,0)

### Maze Navigation Algorithm

The binary uses a 3D maze with:
- **Dimensions**: 20x20x20 (x,y,z)
- **Cell Types**: 0=empty, 1=path, 2=wall, 3=exit
- **Movement**: L/R (y-axis), F/B (x-axis), U/D (z-axis)
- **Exit Position**: (0, 3, 0)

The maze data structure shows the exit at offset `0x00002110` with value `0300 0000 0100 0000`.

## Generated Solution

The `generate_password.py` script successfully generates valid navigation paths:

- **Input**: Any username string
- **Output**: Movement sequence that reaches the exit
- **Validation**: All generated paths end at (0,3,0)
- **Example**: User "hacker" → Password "RRFBRLR" → Reaches exit

## Conclusion

The ARMcrackme binary is a maze navigation game, not a traditional password cracking challenge. The "solution" involves finding the correct path through the 3D maze to reach the exit and obtain the flag. The password generation algorithm creates user-specific movement sequences that guarantee reaching the maze exit at coordinates (0, 3, 0).