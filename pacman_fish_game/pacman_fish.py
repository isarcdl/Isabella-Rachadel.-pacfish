"""
Pac-Man style game: Fish (player) and Sharks (ghosts / enemies)
Assets are expected in a subfolder named "assets".
Run with: python pacman_fish.py
Requires: pygame
"""

import pygame, sys, random, collections, os
from collections import deque

# --- Config ---
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "pacman_fish_assets")
TILE = 32
MAP_W = 41  # odd for maze generation
MAP_H = 31  # odd for maze generation
VIEWPORT_W = 800
VIEWPORT_H = 640
PLAYER_SPEED = 4  # pixels per frame
GHOST_SPEED = 2  # pixels per frame
PATHFIND_INTERVAL = 30  # frames between path updates for sharks

# --- Utilities ---
def load_image(name):
    path = os.path.join(ASSETS_DIR, name)
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception as e:
        print("Failed to load", path, e)
        surf = pygame.Surface((TILE,TILE), pygame.SRCALPHA)
        pygame.draw.rect(surf, (255,0,255), surf.get_rect(), 1)
        return surf

# Maze generation (recursive backtracking) on odd-grid
def make_maze(w, h):
    # w,h should be odd; 1 = wall, 0 = floor
    grid = [[1]*w for _ in range(h)]
    def inside(x,y):
        return 0 <= x < w and 0 <= y < h
    dirs = [(2,0),(-2,0),(0,2),(0,-2)]
    stack = []
    sx, sy = 1,1
    grid[sy][sx] = 0
    stack.append((sx,sy))
    while stack:
        x,y = stack[-1]
        random.shuffle(dirs)
        carved = False
        for dx,dy in dirs:
            nx,ny = x+dx, y+dy
            if inside(nx,ny) and grid[ny][nx] == 1:
                grid[ny][nx] = 0
                grid[y+dy//2][x+dx//2] = 0
                stack.append((nx,ny))
                carved = True
                break
        if not carved:
            stack.pop()
    # create border walls (already walls)
    return grid

# Simple BFS pathfinder on grid (4-neigh)
def bfs(start, goal, grid):
    h = len(grid); w = len(grid[0])
    q = deque([start])
    prev = {start: None}
    while q:
        x,y = q.popleft()
        if (x,y) == goal:
            # reconstruct path
            path = []
            cur = goal
            while cur != start:
                path.append(cur)
                cur = prev[cur]
            path.reverse()
            return path
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx,ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == 0 and (nx,ny) not in prev:
                prev[(nx,ny)] = (x,y)
                q.append((nx,ny))
    return None

# Convert pixel pos to grid and back
def pixel_to_grid(px,py):
    return px//TILE, py//TILE
def grid_to_pixel(gx,gy):
    return gx*TILE, gy*TILE

# --- Pygame initialization ---
pygame.init()
screen = pygame.display.set_mode((VIEWPORT_W, VIEWPORT_H))
pygame.display.set_caption("Pac-Fish")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)

# Load assets
fish_closed = load_image("fish_closed.png")
fish_open = load_image("fish_open.png")
shark_img = load_image("shark.png")
pellet_img = load_image("pellet.png")
seaweed_img = load_image("seaweed.png")
game_over_img = load_image("game_over.png")

# Resize assets to tile size if needed
def fit(img):
    if img.get_width() != TILE or img.get_height() != TILE:
        return pygame.transform.smoothscale(img, (TILE, TILE))
    return img
fish_closed = fit(fish_closed)
fish_open = fit(fish_open)
shark_img = fit(shark_img)
pellet_img = fit(pellet_img)
seaweed_img = fit(seaweed_img)

# --- Map ---
grid = make_maze(MAP_W, MAP_H)
# Place some decorative seaweed in some floor tiles
for y in range(1, MAP_H-1):
    for x in range(1, MAP_W-1):
        if grid[y][x] == 0 and random.random() < 0.04:
            # mark as special (2) for seaweed but keep traversable
            grid[y][x] = 0  # keep 0, we'll draw seaweed separately
# Create pellet list
pellets = set()
for y in range(MAP_H):
    for x in range(MAP_W):
        if grid[y][x] == 0:
            pellets.add((x,y))

# Spawn player at center-ish
player_gx, player_gy = 1,1
player_px, player_py = grid_to_pixel(player_gx, player_gy)
# Animation toggle for mouth
anim_timer = 0
anim_state = 0

# Sharks: spawn at several corners
shark_positions = [(MAP_W-2, MAP_H-2), (MAP_W-2,1), (1, MAP_H-2)]
sharks = []
for gx,gy in shark_positions:
    px,py = grid_to_pixel(gx,gy)
    sharks.append({
        'gx': gx, 'gy': gy, 'px': px, 'py': py,
        'path': [], 'framecount': 0
    })

score = 0
game_over = False
win = False
frame = 0

def draw_map(surface, camera_rect):
    # draw tiles
    ox, oy = camera_rect.topleft
    for y in range(MAP_H):
        for x in range(MAP_W):
            rx = x*TILE - ox; ry = y*TILE - oy
            if rx + TILE < 0 or ry + TILE < 0 or rx > VIEWPORT_W or ry > VIEWPORT_H:
                continue
            if grid[y][x] == 1:
                pygame.draw.rect(surface, (10,50,120), (rx,ry,TILE,TILE))
            else:
                pygame.draw.rect(surface, (0,0,0), (rx,ry,TILE,TILE))
                # pellet
                if (x,y) in pellets:
                    surface.blit(pellet_img, (rx,ry))
                # small chance to show seaweed decor
                if random.random() < 0.001:
                    surface.blit(seaweed_img, (rx,ry))

# --- Main loop ---
running = True
while running:
    dt = clock.tick(60)
    frame += 1
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    keys = pygame.key.get_pressed()
    if not game_over and not win:
        # Player movement (pixel-based with collision)
        dx = dy = 0
        if keys[pygame.K_LEFT]: dx = -PLAYER_SPEED
        if keys[pygame.K_RIGHT]: dx = PLAYER_SPEED
        if keys[pygame.K_UP]: dy = -PLAYER_SPEED
        if keys[pygame.K_DOWN]: dy = PLAYER_SPEED

        # attempt move with collision
        def try_move(px, py, dx, dy):
            nx = px + dx; ny = py + dy
            # check four corners for collision with wall tiles
            corners = [(nx, ny), (nx+TILE-1, ny), (nx, ny+TILE-1), (nx+TILE-1, ny+TILE-1)]
            for cx,cy in corners:
                gx,gy = pixel_to_grid(cx, cy)
                if 0 <= gx < MAP_W and 0 <= gy < MAP_H and grid[gy][gx] == 1:
                    return px, py
            return nx, ny

        player_px, player_py = try_move(player_px, player_py, dx, 0)
        player_px, player_py = try_move(player_px, player_py, 0, dy)

        # collect pellet if on center of tile
        pgx, pgy = pixel_to_grid(player_px + TILE//2, player_py + TILE//2)
        if (pgx, pgy) in pellets:
            pellets.remove((pgx,pgy))
            score += 10

        if not pellets:
            win = True

        # animate mouth
        anim_timer += 1
        if anim_timer > 12:
            anim_timer = 0
            anim_state = 1 - anim_state

        # update sharks
        for s in sharks:
            s['framecount'] += 1
            # recompute path occasionally
            if s['framecount'] % PATHFIND_INTERVAL == 0 or not s['path']:
                start = (s['px']//TILE, s['py']//TILE)
                goal = (player_px//TILE, player_py//TILE)
                path = bfs(start, goal, grid)
                if path:
                    s['path'] = path
                else:
                    s['path'] = []
            # follow path at ghost speed
            if s['path']:
                # move towards next path tile
                nx, ny = s['path'][0]
                target_x, target_y = grid_to_pixel(nx, ny)
                # compute vector
                vx = target_x - s['px']; vy = target_y - s['py']
                dist = (vx*vx + vy*vy) ** 0.5
                if dist < 1:
                    # reached tile
                    s['px'], s['py'] = target_x, target_y
                    s['path'].pop(0)
                else:
                    move_x = GHOST_SPEED * vx / dist
                    move_y = GHOST_SPEED * vy / dist
                    s['px'] += move_x; s['py'] += move_y
            else:
                # random wander
                if random.random() < 0.02:
                    dirs = [(1,0),(-1,0),(0,1),(0,-1)]
                    rx, ry = random.choice(dirs)
                    gnx = s['px']//TILE + rx; gny = s['py']//TILE + ry
                    if 0 <= gnx < MAP_W and 0 <= gny < MAP_H and grid[gny][gnx] == 0:
                        s['path'] = [(gnx,gny)]

        # check collisions with sharks
        pr = pygame.Rect(player_px, player_py, TILE, TILE)
        for s in sharks:
            sr = pygame.Rect(int(s['px']), int(s['py']), TILE, TILE)
            if pr.colliderect(sr):
                game_over = True

    # camera centered on player
    cam_x = int(player_px + TILE/2 - VIEWPORT_W/2)
    cam_y = int(player_py + TILE/2 - VIEWPORT_H/2)
    cam_x = max(0, min(cam_x, MAP_W*TILE - VIEWPORT_W))
    cam_y = max(0, min(cam_y, MAP_H*TILE - VIEWPORT_H))
    camera_rect = pygame.Rect(cam_x, cam_y, VIEWPORT_W, VIEWPORT_H)

    # draw
    screen.fill((0,0,0))
    draw_map(screen, camera_rect)
    # draw sharks
    for s in sharks:
        rx = int(s['px']) - camera_rect.x; ry = int(s['py']) - camera_rect.y
        screen.blit(shark_img, (rx, ry))
    # draw player (animated)
    rx = int(player_px) - camera_rect.x; ry = int(player_py) - camera_rect.y
    if anim_state == 0:
        screen.blit(fish_closed, (rx, ry))
    else:
        screen.blit(fish_open, (rx, ry))
    # UI
    score_surf = font.render(f"Score: {score}", True, (255,255,255))
    screen.blit(score_surf, (10,10))

    if game_over:
        # show game over centered
        go = pygame.transform.smoothscale(game_over_img, (400,200))
        screen.blit(go, (VIEWPORT_W//2 - 200, VIEWPORT_H//2 - 100))
    if win:
        wsurf = font.render("YOU WIN! All pellets eaten.", True, (255,255,0))
        screen.blit(wsurf, (VIEWPORT_W//2 - wsurf.get_width()//2, 20))

    pygame.display.flip()

pygame.quit()
sys.exit()
