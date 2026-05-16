import sys
from collections import deque

def get_next_move(sx, sy, target_x, target_y, grid, width, height):
    # If we are already at the target tile, just stay
    if sx == target_x and sy == target_y:
        return 's'
    
    q = deque([(sx, sy, [])])
    visited = set([(sx, sy)])
    
    # Valid moves and their coordinate changes
    directions = [('u', 0, -1), ('d', 0, 1), ('l', -1, 0), ('r', 1, 0)]
    
    while q:
        x, y, path = q.popleft()
        
        if x == target_x and y == target_y:
            return path[0]  # Return the first step needed to reach the target
        
        for move, dx, dy in directions:
            nx, ny = x + dx, y + dy
            
            if 0 <= nx < width and 0 <= ny < height:
                # Ensure it's not a wall and hasn't been visited
                if grid[ny][nx] != '#' and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    q.append((nx, ny, path + [move]))
                    
    return 's' # Fallback if no path is found

def main():
    # Read the initial map string
    line = input().strip()
    if line.startswith("IN "):
        map_str = line[3:]
    else:
        map_str = line
        
    width, height = 29, 29
    
    # Convert the 1D string into a 2D list for easier pathfinding
    grid = [map_str[i:i+width] for i in range(0, width*height, width)]
    
    # tungtungsahuur's camping coordinate
    target_x, target_y = 12, 12

    # Main game loop
    while True:
        try:
            state = input().strip()
            if not state: 
                break
                
            parts = state.split()
            if parts[0] == "IN":
                # The first 4 tokens after 'IN' belong to this bot (x, y, timer, flag)
                my_x = int(parts[1])
                my_y = int(parts[2])
                
                # Calculate and output the next move
                move = get_next_move(my_x, my_y, target_x, target_y, grid, width, height)
                print(f"OUT {move}")
                
        except EOFError:
            break

if __name__ == "__main__":
    main()