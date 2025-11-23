import pygame, sys, os, math, time
from collections import deque
import random

# --- Config ---
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
TILE = 32
MAP_W = 41
MAP_H = 31
VIEWPORT_W = 800
VIEWPORT_H = 640
PLAYER_SPEED = 4
GHOST_SPEED = 2
PATHFIND_INTERVAL = 30
SHARK_RELEASE_TIME = 600 # 10 segundos * 60 FPS
SHARK_STUN_TIME = 180 # 3 segundos * 60 FPS
PLAYER_LIVES = 3
PURSUIT_RANGE = 8 # Raio de perseguição em tiles
FADE_SPEED = 8

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

def make_fixed_map():
    layout = [
        "111111111111111111111111111111111111111",
        "100000000011000000000011000000000000001",
        "101111111011011111111011011111111110101",
        "101111111000011111111000011111111110101",
        "100000000000000000000000000000000000001",
        "101111011111111011111111011111110111101",
        "100000011000000000000000000000000000001",
        "111111011011111111111111111011011111111",
        "100000011000000000020000000000000000001",  
        "111111011011111111111111111011011111111",
        "100000011000000000000000000000110000001",
        "101111011111111011111111011111110111101",
        "100000000000000000000000000000000000001",
        "101111111011011111111011011111111110101",
        "101111111011011111111011011111111110101",
        "100000000011000000000011000000000000001",
        "111111111111111111111111111111111111111"
    ]
    return [[int(c) for c in row] for row in layout]

def bfs(start, goal, grid):
    h = len(grid); w = len(grid[0])
    q = deque([start])
    prev = {start: None}
    while q:
        x,y = q.popleft()
        if (x,y) == goal:
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

def pixel_to_grid(px,py):
    return px//TILE, py//TILE
def grid_to_pixel(gx,gy):
    return gx*TILE, gy*TILE

# --- Pygame ---
pygame.init()
screen = pygame.display.set_mode((VIEWPORT_W, VIEWPORT_H))
pygame.display.set_caption("Pac-Fish")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 40)

def draw_text_with_shadow(surface, text, color, shadow_color, pos):
    # Desenha a sombra
    shadow_surf = font.render(text, True, shadow_color)
    surface.blit(shadow_surf, (pos[0] + 2, pos[1] + 2))
    # Desenha o texto principal
    text_surf = font.render(text, True, color)
    surface.blit(text_surf, pos)

# Assets
fish_closed = load_image("fish_closed.png")
fish_open = load_image("fish_open.png")
shark_img = load_image("shark.png")
pellet_img = load_image("bolinha.png")
seaweed_img = load_image("alga.png")
background_img = load_image("mar.jpg")

def fit(img):
    if img.get_width() != TILE or img.get_height() != TILE:
        return pygame.transform.smoothscale(img, (TILE, TILE))
    return img

fish_closed = fit(fish_closed)
fish_open = fit(fish_open)
shark_img = fit(shark_img)
pellet_img = fit(pellet_img)
seaweed_img = fit(seaweed_img)
background_img = pygame.transform.smoothscale(background_img, (MAP_W*TILE, MAP_H*TILE))

# --- Map ---
grid = make_fixed_map()
MAP_H = len(grid)
MAP_W = len(grid[0])

def create_pellets():
    pellets = set()
    for y in range(MAP_H):
        for x in range(MAP_W):
            if grid[y][x] == 0:
                pellets.add((x,y))
    return pellets

pellets = create_pellets()

# Player
player_px, player_py = grid_to_pixel(1,1)
anim_timer = 0
anim_state = 0
player_lives = PLAYER_LIVES
score = 0
frame = 0
start_time = None
player_flip = False  # As imagens originais olham para ESQUERDA, então False = esquerda, True = direita

# Sharks
SHARK_SPAWN_POINT = (MAP_W//2, MAP_H//2)
SHARK_COUNT = 3 # Número total de tubarões no jogo
SHARK_START_POSITIONS = [(MAP_W-2, MAP_H-2), (MAP_W-2,1), (1, MAP_H-2)] # Posições iniciais (fora da toca)
def reset_sharks():
    sharks = []
    # Inicializa todos os tubarões na toca
    for i in range(SHARK_COUNT):
        gx, gy = SHARK_SPAWN_POINT
        px, py = grid_to_pixel(gx, gy)
        sharks.append({
            'gx': gx, 'gy': gy, 'px': px, 'py': py,
            'path': [], 'framecount': 0,
            'release_timer': i * SHARK_RELEASE_TIME + SHARK_STUN_TIME, # Libera um a cada 10s + 3s de stun
            'offset_x': 0,
            'flip': False
        })
    return sharks
sharks = reset_sharks()

# Game state
game_over = False
win = False
show_start_screen = True
show_gameover_screen = False
high_score = 0
best_times = []

# --- Fade helper ---
def fade_screen(color=(0,0,0), alpha=0):
    fade_surf = pygame.Surface((VIEWPORT_W, VIEWPORT_H))
    fade_surf.fill(color)
    fade_surf.set_alpha(alpha)
    screen.blit(fade_surf, (0,0))

def draw_map(surface, camera_rect):
    ox, oy = camera_rect.topleft
    for y in range(MAP_H):
        for x in range(MAP_W):
            rx = x*TILE - ox; ry = y*TILE - oy
            if rx + TILE < 0 or ry + TILE < 0 or rx > VIEWPORT_W or ry > VIEWPORT_H:
                continue
            if grid[y][x] == 1:
                surface.blit(seaweed_img, (rx, ry))
            # Fundo do mar aparece em todos os lugares
            if (x,y) in pellets:
                surface.blit(pellet_img, (rx,ry))

fade_alpha = 255
fade_mode = "in"

running = True
while running:
    dt = clock.tick(60)
    frame += 1
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    keys = pygame.key.get_pressed()

    # --- Start Screen ---
    if show_start_screen:
        screen.fill((0,0,64))
        texts = [
            ("PAC-FISH", (255,255,0), -100),
            ("Use as setinhas do seu teclado para se movimentar", (255,255,255), -40),
            ("Colete todas as bolinhas e evite os tubarões!", (255,255,255), 0),
            ("Aperte ESPAÇO para começar!", (255,255,255), 40)
        ]
        for text, color, offset_y in texts:
            surf = font.render(text, True, color)
            screen.blit(surf, ((VIEWPORT_W - surf.get_width())//2, VIEWPORT_H//2 + offset_y))
        if fade_mode == "in":
            fade_alpha -= FADE_SPEED
            if fade_alpha <= 0: fade_alpha = 0; fade_mode = ""
        fade_screen(alpha=fade_alpha)
        pygame.display.flip()
        if keys[pygame.K_SPACE]:
            show_start_screen = False
            fade_alpha = 255
            fade_mode = "in"
            start_time = time.time()
        continue

    # --- Game Over Screen ---
    if show_gameover_screen:
        screen.fill((0,0,64))
        texts = [
            ("GAME OVER", (255,0,0), 150),
            (f"Score Final: {score}", (255,255,255), 220),
            (f"High Score: {high_score}", (255,255,0), 270),
            ("Aperte R para jogar novamente!", (255,255,255), 350)
        ]
        for text, color, y in texts:
            surf = font.render(text, True, color)
            screen.blit(surf, ((VIEWPORT_W - surf.get_width())//2, y))
        if fade_mode == "in":
            fade_alpha -= FADE_SPEED
            if fade_alpha <= 0: fade_alpha = 0; fade_mode = ""
        fade_screen(alpha=fade_alpha)
        pygame.display.flip()
        if keys[pygame.K_r]:
            pellets = create_pellets()
            player_px, player_py = grid_to_pixel(1,1)
            player_lives = PLAYER_LIVES
            score = 0
            frame = 0
            start_time = time.time()
            sharks = reset_sharks()
            game_over = False
            show_gameover_screen = False
            fade_alpha = 255
            fade_mode = "in"
        continue

    # --- Game Logic ---
    if not game_over and not win:
        dx = dy = 0
        if keys[pygame.K_LEFT]: dx = -PLAYER_SPEED
        if keys[pygame.K_RIGHT]: dx = PLAYER_SPEED
        if keys[pygame.K_UP]: dy = -PLAYER_SPEED
        if keys[pygame.K_DOWN]: dy = PLAYER_SPEED

        # CORRIGIDO: As imagens originais olham para ESQUERDA
        # Para olhar DIREITA, precisa fazer flip (True)
        # Para olhar ESQUERDA, não faz flip (False)
        if dx < 0:
            player_flip = False  # Esquerda = sem flip
        elif dx > 0:
            player_flip = True   # Direita = com flip

        def try_move(px, py, dx, dy):
            nx, ny = px + dx, py + dy
            corners = [(nx, ny), (nx+TILE-1, ny), (nx, ny+TILE-1), (nx+TILE-1, ny+TILE-1)]
            for cx, cy in corners:
                gx, gy = pixel_to_grid(cx, cy)
                if 0 <= gx < MAP_W and 0 <= gy < MAP_H and grid[gy][gx] == 1:
                    return px, py
            return nx, ny

        player_px, player_py = try_move(player_px, player_py, dx, 0)
        player_px, player_py = try_move(player_px, player_py, 0, dy)

        pgx, pgy = pixel_to_grid(player_px + TILE//2, player_py + TILE//2)
        if (pgx, pgy) in pellets:
            pellets.remove((pgx, pgy))
            score += 10
        if not pellets:
            win = True
            end_time = time.time()
            elapsed = end_time - start_time
            best_times.append(elapsed)
            best_times.sort()
            if len(best_times) > 3: best_times = best_times[:3]
            fade_alpha = 255
            fade_mode = "in"

        anim_timer += 1
        if anim_timer > 12:
            anim_timer = 0
            anim_state = 1 - anim_state

        for s in sharks:
            if s['release_timer'] > 0:
                s['release_timer'] -= 1
                # Tubarão na toca ou em fase de "stun"
                if s['release_timer'] > SHARK_STUN_TIME:
                    # Tubarão esperando na toca
                    s['offset_x'] = int(4 * math.sin(frame * 0.1))
                else:
                    # Tubarão liberado, mas em "stun" (atraso de 3s)
                    s['offset_x'] = 0 # Para de flutuar
                    # Se o stun acabou, o tubarão é liberado para o jogo.
                    if s['release_timer'] <= 0:
                        # Garante que ele esteja na posição correta do grid antes de começar a se mover
                        gx, gy = SHARK_SPAWN_POINT
                        s['px'], s['py'] = grid_to_pixel(gx, gy)
                        s['gx'], s['gy'] = gx, gy
                        # Força o cálculo do primeiro caminho de perseguição no próximo frame
                        s['framecount'] = PATHFIND_INTERVAL - 1 
                        s['path'] = []
                        
                continue
            s['framecount'] += 1
            if s['framecount'] % PATHFIND_INTERVAL == 0 or not s['path']:
                start = (int(s['px']) // TILE, int(s['py']) // TILE)
                goal = (int(player_px) // TILE, int(player_py) // TILE)
                # Lógica de perseguição condicional
                player_gx, player_gy = pixel_to_grid(player_px + TILE//2, player_py + TILE//2)
                dist_sq = (start[0] - player_gx)**2 + (start[1] - player_gy)**2
                
                # Tubarão só persegue se não estiver na toca (release_timer <= 0)
                if s['release_timer'] <= 0 and dist_sq <= PURSUIT_RANGE**2:
                    # Se o tubarão acabou de sair da toca, ele vai perseguir imediatamente.
                    # Se não, ele usa a lógica de perseguição condicional.
                    # Persegue o jogador
                    goal = (player_gx, player_gy)
                    path = bfs(start, goal, grid)
                    s['path'] = path if path else []
                else:
                    # Movimento aleatório/patrulha
                    if not s['path'] or s['path'][-1] == start:
                        # Se não tem caminho ou chegou ao destino, escolhe um novo aleatório
                        possible_moves = []
                        for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)):
                            nx, ny = start[0] + dx, start[1] + dy
                            if 0 <= nx < MAP_W and 0 <= ny < MAP_H and grid[ny][nx] == 0:
                                possible_moves.append((nx, ny))
                        
                        if possible_moves:
                            next_tile = random.choice(possible_moves)
                            s['path'] = [next_tile]
                        else:
                            s['path'] = [] # Preso, não se move
            if s['path']:
                nx, ny = s['path'][0]
                target_x, target_y = grid_to_pixel(nx, ny)
                vx = target_x - s['px']; vy = target_y - s['py']
                dist = (vx*vx + vy*vy)**0.5
                if dist < 1:
                    s['px'], s['py'] = target_x, target_y
                    s['path'].pop(0)
                else:
                    s['px'] += GHOST_SPEED * vx / dist
                    s['py'] += GHOST_SPEED * vy / dist
                # A imagem original do tubarão provavelmente olha para a esquerda.
                # Para olhar para a direita, precisamos de flip=True.
                s['flip'] = vx > 0

        pr = pygame.Rect(player_px, player_py, TILE, TILE)
        for s in sharks:
            if s['release_timer'] > 0: continue
            sr = pygame.Rect(int(s['px']), int(s['py']), TILE, TILE)
            if pr.colliderect(sr):
                player_lives -= 1
                if player_lives <= 0:
                    game_over = True
                    high_score = max(high_score, score)
                    show_gameover_screen = True
                    fade_alpha = 255
                    fade_mode = "in"
                else:
                    player_px, player_py = grid_to_pixel(1,1)
                    sharks = reset_sharks()

    # --- Camera ---
    cam_x = max(0, min(int(player_px + TILE/2 - VIEWPORT_W/2), MAP_W*TILE - VIEWPORT_W))
    cam_y = max(0, min(int(player_py + TILE/2 - VIEWPORT_H/2), MAP_H*TILE - VIEWPORT_H))
    camera_rect = pygame.Rect(cam_x, cam_y, VIEWPORT_W, VIEWPORT_H)

    # --- Draw ---
    screen.blit(background_img, (-camera_rect.x, -camera_rect.y))
    draw_map(screen, camera_rect)
    for s in sharks:
        rx = int(s['px']) - camera_rect.x + s.get('offset_x',0)
        ry = int(s['py']) - camera_rect.y
        img = pygame.transform.flip(shark_img, s['flip'], False)
        screen.blit(img, (rx, ry))
    # Player com flip correto
    screen.blit(
        pygame.transform.flip(fish_closed if anim_state==0 else fish_open, player_flip, False),
        (int(player_px)-camera_rect.x, int(player_py)-camera_rect.y)
    )
    draw_text_with_shadow(screen, f"Score: {score}  Lives: {player_lives}", (255, 255, 255), (0, 0, 0), (10, 10))

    # --- Win Screen ---
    if win:
        screen.fill((0,0,64))
        texts = [
            ("VOCÊ VENCEU!", (0,255,0), 150),
            (f"Tempo: {best_times[0]:.2f} s", (255,255,255), 250),
            ("Melhores tempos:", (255,255,0), 300)
        ]
        for i, t in enumerate(best_times):
            texts.append((f"{i+1}. {t:.2f} s", (255,255,255), 340 + i*30))
        texts.append(("Aperte R para jogar novamente!", (255,255,255), 440))
        for text, color, y in texts:
            surf = font.render(text, True, color)
            screen.blit(surf, ((VIEWPORT_W - surf.get_width())//2, y))
        fade_screen(alpha=fade_alpha)
        if fade_mode == "in":
            fade_alpha -= FADE_SPEED
            if fade_alpha <= 0: fade_alpha = 0; fade_mode = ""
        if keys[pygame.K_r]:
            pellets = create_pellets()
            player_px, player_py = grid_to_pixel(1,1)
            player_lives = PLAYER_LIVES
            score = 0
            frame = 0
            start_time = time.time()
            sharks = reset_sharks()
            win = False
            fade_alpha = 255
            fade_mode = "in"

    pygame.display.flip()

pygame.quit()
sys.exit()
