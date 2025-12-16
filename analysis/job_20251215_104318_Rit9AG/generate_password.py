#!/usr/bin/env python3
"""
Password Generator for ARMcrackme Maze Navigation

This script generates the "password" (sequence of moves) required to navigate
through the 3D maze from the starting position (0, 0, 0) to the exit.

Based on the reverse engineering analysis, the exit is located at position (0, 3, 0).
The maze structure shows a clear path from start to exit.
"""

def generate_password(user_input: str) -> str:
    """
    Generate password based on user input for the ARMcrackme maze navigation.
    
    Since this is a maze navigation game rather than a traditional password system,
    the "password" represents the optimal path through the maze.
    
    Args:
        user_input (str): User identifier (used for path variation)
        
    Returns:
        str: Sequence of navigation commands to reach the maze exit
    """
    
    # Hash the user input to create variation in path
    user_hash = sum(ord(c) for c in user_input) % 4
    
    # Base path from (0,0,0) to exit at (0,3,0) - all paths end at (0,3,0)
    # This is based on the maze analysis showing the exit at coordinates (0, 3, 0)
    base_paths = [
        "RRR",              # Direct path: (0,0,0) -> (0,1,0) -> (0,2,0) -> (0,3,0)
        "RRLR",             # Path: (0,0,0) -> (0,1,0) -> (0,2,0) -> (0,1,0) -> (0,2,0) -> (0,3,0)
        "RRFBR",            # Path: (0,0,0) -> (0,1,0) -> (0,2,0) -> (1,2,0) -> (0,2,0) -> (0,3,0)
        "RUDRR",            # Path: (0,0,0) -> (0,0,1) -> (0,0,0) -> (0,1,0) -> (0,2,0) -> (0,3,0)
    ]
    
    # Select path based on user input hash
    selected_path = base_paths[user_hash]
    
    # Add complexity based on user input characteristics but ensure final destination
    prefix = ""
    suffix = ""
    
    if len(user_input) > 8:
        # For long usernames, add vertical movement before the main path
        prefix = "UD"
    
    if any(c.lower() in 'aeiou' for c in user_input):
        # For usernames with vowels, add a small detour
        suffix = "LR"
    
    # Ensure we still reach the exit by adding corrective moves
    full_path = prefix + selected_path + suffix
    
    # Calculate final position and adjust if needed
    final_coords = get_maze_coordinates(full_path)[-1]
    if final_coords != (0, 3, 0):
        # Add corrective moves to reach exit
        x, y, z = final_coords
        while y < 3:
            full_path += "R"
            y += 1
        while y > 3:
            full_path += "L"
            y -= 1
        while x > 0:
            full_path += "B"
            x -= 1
        while z > 0:
            full_path += "D"
            z -= 1
    
    return full_path

def get_maze_coordinates(path: str) -> list:
    """
    Convert a path string to coordinate movements.
    
    Args:
        path (str): Movement path string
        
    Returns:
        list: List of (x, y, z) coordinates along the path
    """
    coordinates = [(0, 0, 0)]  # Starting position
    x, y, z = 0, 0, 0
    
    moves = {
        'L': (0, -1, 0),  # Left
        'R': (0, 1, 0),   # Right  
        'F': (1, 0, 0),   # Forward
        'B': (-1, 0, 0),  # Back
        'U': (0, 0, 1),   # Up
        'D': (0, 0, -1),  # Down
    }
    
    for move in path:
        if move in moves:
            dx, dy, dz = moves[move]
            x += dx
            y += dy 
            z += dz
            coordinates.append((x, y, z))
    
    return coordinates

def validate_path(path: str) -> bool:
    """
    Validate if the path leads to the exit position (0, 3, 0).
    
    Args:
        path (str): Movement path string
        
    Returns:
        bool: True if path reaches exit, False otherwise
    """
    final_coords = get_maze_coordinates(path)[-1]
    return final_coords == (0, 3, 0)

def main():
    """
    Main function to demonstrate password generation.
    """
    # Example usage
    test_users = ["admin", "user", "alice", "bob", "testuser"]
    
    print("ARMcrackme Password Generation")
    print("=" * 40)
    print("Movement Commands:")
    print("L = Left, R = Right, F = Forward")
    print("B = Back, U = Up, D = Down")
    print()
    
    for user in test_users:
        password = generate_password(user)
        coords = get_maze_coordinates(password)
        valid = validate_path(password)
        
        print(f"User: {user}")
        print(f"Password: {password}")
        print(f"Path: {' -> '.join(str(coord) for coord in coords)}")
        print(f"Reaches Exit: {valid}")
        print("-" * 30)

if __name__ == "__main__":
    main()