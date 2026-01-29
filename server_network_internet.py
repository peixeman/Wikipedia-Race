import argparse
import json
from mediawikiapi import MediaWikiAPI
import os
import random
import socket
import string
import time
import threading


# Server configuration
TCP_PORT = int(os.environ.get("PORT", 5555))
BUFFER_SIZE = 4096

PLAYER_STATS_FILE = "wiki_race_player_stats.json"


class WikiRaceServer:
    def __init__(self, headless=False):
        self.lobbies = {}  # {lobby_code: LobbyData}
        self.server_socket = None
        self.running = True
        self.mediawiki = MediaWikiAPI()
        self.headless = headless
        self.player_stats = self.load_player_stats()


    def load_player_stats(self):
        """Load persistent player stats from disk"""
        if not os.path.exists(PLAYER_STATS_FILE):
            return {}

        try:
            with open(PLAYER_STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"Failed to load stats file: {e}")

        return {}


    def save_player_stats(self):
        """Save persistent player stats to disk"""
        try:
            with open(PLAYER_STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.player_stats, f, indent=2)
        except Exception as e:
            print(f"Failed to save stats file: {e}")


    def ensure_player_stats(self, player_name):
        """Ensure a player exists in the stats dict"""
        if player_name not in self.player_stats:
            self.player_stats[player_name] = {
                "points": 0,
                "wins": 0,
                "clicks": 0,
                "games_played": 0,
                "time_played": 0.0
            }

    def reset_player_stats(self):
        """Delete the stats JSON file and clear in-memory stats"""
        print("Resetting player stats...")
        self.player_stats = {}

        try:
            if os.path.exists(PLAYER_STATS_FILE):
                os.remove(PLAYER_STATS_FILE)
                print(f"Deleted {PLAYER_STATS_FILE}")
        except Exception as e:
            print(f"Failed to delete stats file: {e}")


    def generate_lobby_code(self):
        """Generate a unique 4-character lobby code"""
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if code not in self.lobbies:
                return code


    def get_local_ip(self):
        """Get the local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"


    def create_lobby(self):
        """Create a new lobby"""
        lobby_code = self.generate_lobby_code()
        self.lobbies[lobby_code] = {
            "clients": {},  # {client_socket: {"name": str, "ready": bool}}
            "article_requests": {},
            "game_results": {},
            "game_active": False
        }
        print(f"Created lobby: {lobby_code}")
        return lobby_code


    def lobby_countdown(self, lobby_code):
        lobby = self.lobbies[lobby_code]
        start = time.time()

        while time.time() - start < 10:
            if lobby_code not in self.lobbies:
                return
            if not all(c["ready"] for c in lobby["clients"].values()):
                lobby["countdown_running"] = False
                return
            time.sleep(0.25)

        if lobby_code in self.lobbies and all(c["ready"] for c in lobby["clients"].values()):
            self.start_game(lobby_code)

        lobby["countdown_running"] = False


    def start_tcp_server(self):
        """Start TCP server to accept client connections"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", TCP_PORT))
        self.server_socket.listen(10)

        print(f"Server listening on {self.get_local_ip()}:{TCP_PORT}")
        print("Waiting for connections...")

        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client_socket, address = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_socket, address), daemon=True).start()
            except socket.timeout:
                continue
            except:
                break


    def handle_client(self, client_socket, address):
        """Handle individual client connections"""
        print(f"Client connected from {address}")
        client_lobby = None

        try:
            while self.running:
                data = client_socket.recv(BUFFER_SIZE).decode()
                if not data:
                    break

                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "join":
                    player_name = message.get("name", f"Player{random.randint(1000, 9999)}")
                    lobby_code = message.get("lobby_code")
                    
                    # Create lobby if it doesn't exist
                    if lobby_code not in self.lobbies and lobby_code != "NG":
                        print("Rejected lobby join, no lobby found")
                    else:
                        if lobby_code == "NG":
                            lobby_code = self.create_lobby()
                        client_lobby = lobby_code
                        lobby = self.lobbies[lobby_code]

                        lobby["clients"][client_socket] = {
                            "name": player_name,
                            "address": address,
                            "ready": False
                        }

                        self.ensure_player_stats(player_name)
                        self.save_player_stats()

                        print(f"{player_name} joined lobby {lobby_code}")
                        self.send_message(client_socket, {
                            "type": "join_success",
                            "lobby_code": lobby_code,
                            "message": f"Connected to lobby {lobby_code}"
                        })
                elif msg_type == "article_request":
                    if client_lobby and client_lobby in self.lobbies:
                        lobby = self.lobbies[client_lobby]
                        lobby["article_requests"][client_socket] = message.get("article", "")
                        lobby["clients"][client_socket]["ready"] = True
                        print(f"{lobby["clients"][client_socket]["name"]} submitted article request")

                        if all(c["ready"] for c in lobby["clients"].values()):
                            if "all_ready_time" not in lobby or lobby["all_ready_time"] is None:
                                lobby["all_ready_time"] = time.time()
                        else:
                            lobby["all_ready_time"] = None

                        if all(c["ready"] for c in lobby["clients"].values()):
                            if not lobby.get("countdown_running", False):
                                lobby["countdown_running"] = True
                                threading.Thread(target=self.lobby_countdown, args=(client_lobby,), daemon=True).start()
                elif msg_type == "game_result":
                    if client_lobby and client_lobby in self.lobbies:
                        lobby = self.lobbies[client_lobby]
                        lobby["game_results"][client_socket] = {
                            "status": message.get("status"),
                            "clicks": message.get("clicks"),
                            "time": message.get("time"),
                            "articles": message.get("articles", [])
                        }
                        print(f"{lobby["clients"][client_socket]["name"]} finished")

                        # Check if all players finished
                        if len(lobby["game_results"]) == len(lobby["clients"]):
                            print(f"All players finished in lobby {client_lobby}")
                            self.calculate_and_send_results(client_lobby)
                elif msg_type == "play_again":
                    if client_lobby and client_lobby in self.lobbies:
                        lobby = self.lobbies[client_lobby]
                        lobby["clients"][client_socket]["ready"] = False
                        lobby["article_requests"].pop(client_socket, None)
                        lobby["game_results"].pop(client_socket, None)
                        print(f"{lobby["clients"][client_socket]["name"]} wants to play again")

        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            if client_lobby and client_lobby in self.lobbies:
                self.remove_client(client_socket, client_lobby)


    def send_message(self, client_socket, message):
        """Send JSON message to a client"""
        try:
            client_socket.send(json.dumps(message).encode())
        except:
            pass


    def broadcast_to_lobby(self, lobby_code, message):
        """Send message to all clients in a lobby"""
        if lobby_code not in self.lobbies:
            return
        
        lobby = self.lobbies[lobby_code]
        for client in list(lobby["clients"].keys()):
            self.send_message(client, message)


    def remove_client(self, client_socket, lobby_code):
        """Remove disconnected client"""
        if lobby_code not in self.lobbies:
            return
            
        lobby = self.lobbies[lobby_code]
        if client_socket in lobby["clients"]:
            print(f"Client {lobby["clients"][client_socket]["name"]} disconnected from lobby {lobby_code}")
            del lobby["clients"][client_socket]
            lobby["article_requests"].pop(client_socket, None)
            lobby["game_results"].pop(client_socket, None)
            
            # Delete lobby if empty
            if len(lobby["clients"]) == 0:
                print(f"Lobby {lobby_code} is empty, deleting...")
                del self.lobbies[lobby_code]
                self.reset_player_stats()
        
        try:
            client_socket.close()
        except:
            pass


    def start_game(self, lobby_code):
        """Start the game in a specific lobby"""
        if lobby_code not in self.lobbies:
            return
            
        lobby = self.lobbies[lobby_code]
        if len(lobby["clients"]) == 0:
            return

        if lobby["game_active"]:
            return

        # Collect all article requests
        requests = []
        for client_socket, article in lobby["article_requests"].items():
            if article and article.strip():
                search_results = self.mediawiki.search(article)
                if len(search_results) > 0:
                    requests.append(search_results[0])

        # Add random articles if needed
        while len(requests) < 2:
            random_articles = self.mediawiki.random(1)
            if isinstance(random_articles, str):
                requests.append(random_articles)
            else:
                requests.extend(random_articles)

        # Pick start and end articles
        if len(requests) == 2:
            start_article = requests[1]
            end_article = requests[0]
        else:
            selected = random.sample(requests, 2)
            start_article = selected[0]
            end_article = selected[1]

        print(f"Lobby {lobby_code} game starting: {start_article} -> {end_article}")

        # Send to all clients in lobby
        self.broadcast_to_lobby(lobby_code, {
            "type": "game_start",
            "start_article": start_article,
            "end_article": end_article
        })

        lobby["game_active"] = True
        lobby["game_results"].clear()


    def calculate_and_send_results(self, lobby_code):
        """Calculate scores and send results to all clients in a lobby"""
        if lobby_code not in self.lobbies:
            return
            
        lobby = self.lobbies[lobby_code]
        results = []

        for client_socket, result in lobby["game_results"].items():
            player_name = lobby["clients"][client_socket]["name"]

            # Calculate score
            if result["status"] == "Win":
                score = int(result["clicks"] + (result["time"] / 5))
            elif result["status"] == "Fold":
                score = int(result["clicks"] + result["time"] + 100)
            else:
                score = 350

            self.ensure_player_stats(player_name)

            self.player_stats[player_name]["points"] += score
            self.player_stats[player_name]["games_played"] += 1
            self.player_stats[player_name]["clicks"] += int(result["clicks"])
            self.player_stats[player_name]["time_played"] += round(float(result["time"]))
            if result["status"] == "Win":
                self.player_stats[player_name]["wins"] += 1

            total_points = self.player_stats[player_name]["points"]

            results.append({
                "name": player_name,
                "status": result["status"],
                "clicks": result["clicks"],
                "time": result["time"],
                "score": score,
                "total_points": total_points
            })

        self.save_player_stats()

        # Sort by score
        results.sort(key=lambda x: x["total_points"])

        # Assign rankings
        for i, result in enumerate(results):
            result["rank"] = i + 1

        print(f"Lobby {lobby_code} final results:", results)

        # Send results to all clients in lobby
        self.broadcast_to_lobby(lobby_code, {
            "type": "game_results",
            "results": results
        })

        lobby["game_active"] = False


    def run(self):
        """Run the server"""
        print("="*50)
        print("Wikipedia Race Server - Internet Mode")
        print("="*50)
        
        # Start TCP server thread
        threading.Thread(target=self.start_tcp_server, daemon=True).start()

        if self.headless:
            # Headless mode - just keep running
            print("Running in headless mode. Press Ctrl+C to stop.")
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
                self.running = False
        else:
            # Interactive mode - can create lobbies manually
            print("\nCommands:")
            print("  create - Create a new lobby")
            print("  list   - List active lobbies")
            print("  quit   - Shutdown server")
            print()
            
            while self.running:
                try:
                    cmd = input("> ").strip().lower()
                    
                    if cmd == "create":
                        lobby_code = self.create_lobby()
                        print(f"Created lobby: {lobby_code}")
                    
                    elif cmd == "list":
                        if not self.lobbies:
                            print("No active lobbies")
                        else:
                            for code, lobby in self.lobbies.items():
                                print(f"Lobby {code}: {len(lobby["clients"])} players")
                    
                    elif cmd == "quit":
                        print("Shutting down...")
                        self.running = False
                        break
                    
                except KeyboardInterrupt:
                    print("\nShutting down...")
                    self.running = False
                    break

        # Cleanup
        if self.server_socket:
            self.server_socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wikipedia Race Server")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no input)")
    args = parser.parse_args()
    
    server = WikiRaceServer(headless=args.headless)
    server.run()
