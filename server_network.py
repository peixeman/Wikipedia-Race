import customtkinter
import json
from mediawikiapi import MediaWikiAPI
import os
import random
import socket
import string
import time
import threading


# Server configuration
TCP_PORT = 5555
UDP_BROADCAST_PORT = 5556
BUFFER_SIZE = 4096

# Persistent player stats file
PLAYER_STATS_FILE = "wiki_race_player_stats.json"


class WikiRaceServer:
    def __init__(self):
        self.lobby_code = self.generate_lobby_code()
        self.clients = {}
        self.article_requests = {}
        self.game_results = {}
        self.server_socket = None
        self.udp_socket = None
        self.running = True
        self.game_active = False
        self.mediawiki = MediaWikiAPI()

        # Persistent stats
        self.player_stats = self.load_player_stats()

        # GUI
        self.root = None
        self.status_label = None
        self.players_listbox = None
        self.start_button = None
        self.reset_stats_button = None


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

        self.update_status("Player stats reset.")


    def generate_lobby_code(self):
        """Generate a 4-character lobby code"""
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=4))


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


    def broadcast_server_presence(self):
        """UDP broadcast for server auto-discovery"""
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        broadcast_data = json.dumps({
            "type": "server_discovery",
            "lobby_code": self.lobby_code,
            "ip": self.get_local_ip(),
            "port": TCP_PORT
        }).encode()

        while self.running:
            try:
                self.udp_socket.sendto(broadcast_data, ("<broadcast>", UDP_BROADCAST_PORT))
                time.sleep(2)  # Broadcast every 2 seconds
            except:
                pass


    def start_tcp_server(self):
        """Start TCP server to accept client connections"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", TCP_PORT))
        self.server_socket.listen(10)

        print(f"Server listening on {self.get_local_ip()}:{TCP_PORT}")

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

        try:
            while self.running:
                data = client_socket.recv(BUFFER_SIZE).decode()
                if not data:
                    break

                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "join":
                    player_name = message.get("name", f"Player{len(self.clients) + 1}")
                    self.clients[client_socket] = {
                        "name": player_name,
                        "address": address,
                        "ready": False
                    }

                    # Ensure stats exist
                    self.ensure_player_stats(player_name)
                    self.save_player_stats()

                    self.update_player_list()
                    self.send_message(client_socket, {"type": "join_success", "message": "Connected to lobby"})

                elif msg_type == "article_request":
                    self.article_requests[client_socket] = message.get("article", "")
                    self.clients[client_socket]["ready"] = True
                    self.update_player_list()
                    print(f"Received article request from {self.clients[client_socket]["name"]}: {message.get("article")}")

                elif msg_type == "game_result":
                    self.game_results[client_socket] = {
                        "status": message.get("status"),
                        "clicks": message.get("clicks"),
                        "time": message.get("time"),
                        "articles": message.get("articles", [])
                    }
                    print(f"Received result from {self.clients[client_socket]["name"]}")

                    # Check if all players have finished
                    if len(self.game_results) == len(self.clients):
                        print("All players finished")
                        self.calculate_and_send_results()

                elif msg_type == "play_again":
                    self.clients[client_socket]["ready"] = False
                    self.article_requests.pop(client_socket, None)
                    self.game_results.pop(client_socket, None)
                    self.update_player_list()

        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            self.remove_client(client_socket)


    def send_message(self, client_socket, message):
        """Send JSON message to a client"""
        try:
            client_socket.send(json.dumps(message).encode())
        except:
            pass


    def broadcast_message(self, message):
        """Send message to all connected clients"""
        for client in list(self.clients.keys()):
            self.send_message(client, message)


    def remove_client(self, client_socket):
        """Remove disconnected client"""
        if client_socket in self.clients:
            print(f"Client {self.clients[client_socket]["name"]} disconnected")
            del self.clients[client_socket]
            self.article_requests.pop(client_socket, None)
            self.game_results.pop(client_socket, None)
            self.update_player_list()
        try:
            client_socket.close()
        except:
            pass


    def start_game(self):
        """Start the game, pick articles, and send to all clients"""
        if len(self.clients) == 0:
            return

        # Collect all article requests
        requests = []
        for client_socket, article in self.article_requests.items():
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

        print(f"Game starting: {start_article} -> {end_article}")

        # Send to all clients
        self.broadcast_message({
            "type": "game_start",
            "start_article": start_article,
            "end_article": end_article
        })

        self.game_active = True
        self.game_results.clear()
        self.update_status(f"Game in progress: {start_article} → {end_article}")


    def calculate_and_send_results(self):
        """Calculate scores and send results to all clients"""
        results = []

        # First compute per-round scores and update stats JSON
        for client_socket, result in self.game_results.items():
            player_name = self.clients[client_socket]["name"]
            self.ensure_player_stats(player_name)

            # Calculate per-round score
            if result["status"] == "Win":
                score = int(result["clicks"] + (result["time"] / 5))
            elif result["status"] == "Fold":
                score = int(result["clicks"] + (result["time"]) + 100)
            else:
                score = 350

            # Update persistent stats
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

        # Save stats file after updating
        self.save_player_stats()

        # Sort by total points
        results.sort(key=lambda x: x["total_points"])

        # Assign rankings
        for i, result in enumerate(results):
            result["rank"] = i + 1

        print("Final Results:", results)

        # Send results to all clients
        self.broadcast_message({
            "type": "game_results",
            "results": results
        })

        self.game_active = False
        self.update_status("Game finished! Waiting for next round...")


    # ========== GUI Methods ==========
    def create_gui(self):
        """Create the server GUI"""
        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")

        self.root = customtkinter.CTk()
        self.root.title("Wikipedia Race - Server")
        self.root.geometry("600x550")
        self.root.resizable(False, False)

        # Lobby code display
        code_frame = customtkinter.CTkFrame(self.root)
        code_frame.pack(pady=20, padx=20, fill="x")

        customtkinter.CTkLabel(code_frame, text="Lobby Code:", font=("Arial", 20)).pack()
        customtkinter.CTkLabel(code_frame, text=self.lobby_code, font=("Arial", 40, "bold")).pack()
        customtkinter.CTkLabel(code_frame, text=f"Server IP: {self.get_local_ip()}:{TCP_PORT}",
                               font=("Arial", 12)).pack()

        # Status
        self.status_label = customtkinter.CTkLabel(self.root, text="Waiting for players...",
                                                   font=("Arial", 14))
        self.status_label.pack(pady=10)

        # Players list
        players_frame = customtkinter.CTkFrame(self.root)
        players_frame.pack(pady=10, padx=20, fill="both", expand=True)

        customtkinter.CTkLabel(
            players_frame,
            text="Connected Players:",
            font=("Arial", 16, "bold")
        ).pack(pady=5)

        self.players_listbox = customtkinter.CTkTextbox(players_frame,
                                                        height=200,
                                                        state="disabled")
        self.players_listbox.pack(pady=5, padx=10, fill="both", expand=True)

        # Start button
        self.start_button = customtkinter.CTkButton(
            self.root,
            text="Start Game",
            command=lambda: self.start_game(),
            font=("Arial", 16),
            state="disabled")
        self.start_button.pack(pady=10)

        # Reset stats button
        self.reset_stats_button = customtkinter.CTkButton(
            self.root,
            text="Reset Player Stats",
            command=self.reset_player_stats,
            fg_color="gray",
            font=("Arial", 14)
        )
        self.reset_stats_button.pack(pady=5)

        # Quit button
        customtkinter.CTkButton(
            self.root,
            text="Quit Server",
            command=lambda: self.shutdown(),
            fg_color="red"
        ).pack(pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)


    def update_player_list(self):
        """Update the players list in GUI"""
        if self.root:
            self.root.after(0, self._update_player_list_ui)


    def _update_player_list_ui(self):
        """Internal method to update UI (must run in main thread)"""
        self.players_listbox.configure(state="normal")
        self.players_listbox.delete("1.0", "end")
        for client_socket, info in self.clients.items():
            ready_status = "✓" if info["ready"] else "o"
            self.players_listbox.insert("end", f"{ready_status} {info["name"]}\n")
        self.players_listbox.configure(state="disabled")


        # Enable start button if all players are ready
        all_ready = len(self.clients) > 0 and all(c["ready"] for c in self.clients.values())
        self.start_button.configure(state="normal" if all_ready and not self.game_active else "disabled")


    def update_status(self, message):
        """Update status label"""
        if self.status_label:
            self.root.after(0, lambda: self.status_label.configure(text=message))


    def shutdown(self):
        """Shutdown the server"""
        print("Shutting down server...")
        self.running = False

        # Close all client connections
        for client in list(self.clients.keys()):
            try:
                client.close()
            except:
                pass

        # Close sockets
        if self.server_socket:
            self.server_socket.close()
        if self.udp_socket:
            self.udp_socket.close()

        if self.root:
            self.root.destroy()


    def run(self):
        """Run the server"""
        # Start UDP broadcast thread
        threading.Thread(target=self.broadcast_server_presence, daemon=True).start()

        # Start TCP server thread
        threading.Thread(target=self.start_tcp_server, daemon=True).start()

        # Create and run GUI
        self.create_gui()
        self.root.mainloop()


if __name__ == "__main__":
    server = WikiRaceServer()

    server.run()
