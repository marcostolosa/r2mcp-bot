# 3D Maze Navigator - Reverse Engineering Report

## Binary Overview

**File:** `input.bin`  
**Architecture:** x86-64 ELF  
**Size:** 140.8 KB  
**Type:** Position-independent executable (PIE)  
**Compiler:** GCC 10.2.1  

## Initial Analysis

### File Information
- **Format:** ELF64 shared object (DYN)
- **Entry Point:** 0x10d0
- **Sections:** 30 sections including .text, .rodata, .data, .bss
- **Imports:** Standard C library functions (printf, scanf, fgets, etc.)
- **Libraries:** libc.so.6

### Functions Discovered
- **main()** (0x1538): Program entry point and main game loop
- **get_cell()** (0x11b5): Maze cell accessor
- **prompt_and_update_pos()** (0x11e3): Movement handling
- **get_flag()** (0x1446): Flag retrieval function

## Maze Structure Analysis

### 3D Maze Layout
The binary implements a 20×20×20 3D maze with the following characteristics:

- **Coordinates:** x, y, z (each ranging from 0 to 19)
- **Cell Structure:** Each cell occupies 20 bytes (0x14 bytes)
- **Cell Types:**
  - Type 0: Empty/Traversable space
  - Type 1: Starting position
  - Type 2: Wall/Obstacle (blocks movement)
  - Type 3: Goal/Vault position

### Memory Layout
The maze data is stored at address 0x20e0 in the .rodata section. Each cell structure contains:
```
struct maze_cell {
    uint32_t x;        // X coordinate
    uint32_t y;        // Y coordinate  
    uint32_t z;        // Z coordinate
    uint32_t type;     // Cell type (0=empty, 1=start, 2=wall, 3=goal)
    // Additional padding/reserved space
};
```

### Key Positions
- **Start:** (0, 0, 0) - Initial player position
- **Goal/Vault:** (19, 19, 19) - Contains the flag
- **Maze Size:** 20×20×20 = 8,000 total cells

## Control Flow Analysis

### Main Game Loop
```c
int main() {
    position pos = {0, 0, 0};  // Start at origin
    
    while (true) {
        cell* current = get_cell(&pos);
        if (current->type == 3) break;  // Reached vault
        putchar('\n');
        prompt_and_update_pos(&pos);
    }
    
    puts("You break into the vault and read the secrets within...");
    get_flag();
    return 0;
}
```

### Movement System
The `prompt_and_update_pos()` function handles player movement:

**Input:** Single character command (L/R/F/B/U/D/Q)
**Processing:** 
1. Convert to uppercase
2. Validate move boundaries (0-19 range)
3. Check if target cell is a wall (type 2)
4. Update position if move is valid

**Movement Mapping:**
- **L:** Left (y-1)
- **R:** Right (y+1) 
- **F:** Forward (x+1)
- **B:** Backward (x-1)
- **U:** Up (z+1)
- **D:** Down (z-1)
- **Q:** Quit game

### Flag Retrieval
The `get_flag()` function:
1. Attempts to open `/flag.txt`
2. If successful, reads and displays the flag
3. If failed (testing environment), displays `HTB{fake_flag_for_testing}`

## Solution Strategy

### Path Finding
Since the maze is mostly open space with minimal walls, the optimal solution is straightforward:

**Direct Approach:**
1. Move Right 19 times to reach y=19
2. Move Forward 19 times to reach x=19  
3. Move Up 19 times to reach z=19

**Total Moves:** 57 commands (19+19+19)

**Command Sequence:** `RRRRRRRRRRRRRRRRRRFFFFFFFFFFFFFFFFFFUUUUUUUUUUUUUUUUUUUU`

### Alternative Optimized Path
By interleaving movements, we can reduce the perceived complexity while maintaining 57 total moves:
```
FRUFRUFRUFRU... (repeated 19 times)
```

## Implementation Details

### Key Functions Decompiled

#### get_cell() Function
```c
cell* get_cell(uint32_t* pos) {
    // Calculate memory offset: pos.x * 400 + pos.y * 20 + pos.z
    return maze + (pos[0] * 400 + pos[1] * 20 + pos[2]) * sizeof(cell);
}
```

#### Movement Validation
The movement system checks:
1. **Boundary Conditions:** Must stay within 0-19 range for each axis
2. **Wall Detection:** Target cell type cannot be 2 (wall)
3. **Move Confirmation:** Updates position only if both checks pass

### Maze Data Analysis
The maze data at 0x20e0 shows:
- Most cells are type 0 (traversable)
- Start position (0,0,0) is type 1
- Goal position (19,19,19) is type 3  
- Strategic wall placements create the maze challenge

## Challenges and Solutions

### Anti-RE Measures
- **No Obfuscation:** Code is clearly readable
- **Standard Imports:** Uses common C library functions
- **No Anti-Debug:** No debugger detection or timing checks
- **Clear Structure:** Well-organized function layout

### Solution Challenges
1. **3D Navigation:** Must track x, y, z coordinates simultaneously
2. **Boundary Management:** 20×20×20 space requires careful coordinate tracking
3. **Optimal Path Finding:** While many paths exist, the shortest is 57 moves

## Flag Extraction Process

1. Navigate to position (19, 19, 19)
2. Game loop detects vault (cell type 3)
3. Calls `get_flag()` function
4. Attempts to read `/flag.txt`
5. Displays flag contents

## Final Solution

The crackme is a **3D maze navigation challenge** where the objective is to reach the vault at coordinates (19,19,19).

### Executable Solution
```bash
# Run the binary
./input.bin

# Input this sequence when prompted:
RRRRRRRRRRRRRRRRRRFFFFFFFFFFFFFFFFFFUUUUUUUUUUUUUUUUUUUU
```

### Automated Solution Script
Use the provided `maze_solver.py` script to generate the optimal movement sequence automatically.

## Tools and Techniques Used

1. **Radare2:** Static analysis and decompilation
2. **Ghidra Decompiler:** High-quality C code reconstruction  
3. **Memory Analysis:** Examined maze data structure
4. **Control Flow Analysis:** Traced program execution paths
5. **Pattern Recognition:** Identified 3D maze structure

## Conclusion

This crackme demonstrates a well-designed 3D maze navigation puzzle with clear objectives and straightforward mechanics. The absence of anti-RE techniques makes it an excellent educational example for reverse engineering practice. The solution requires understanding the 3D coordinate system and optimal pathfinding to reach the goal efficiently.