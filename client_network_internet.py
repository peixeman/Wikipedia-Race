import customtkinter
import json
from pygame import mixer
import socket
import subprocess
import sys
import threading

import client_main as clm
import client_requests as clr


# Server configuration
SERVER_ADDRESS = "crossover.proxy.rlwy.net"
TCP_PORT = 20904
BUFFER_SIZE = 4096


class WikiRaceClient:
    def __init__(self, name=None, connected=False, running=True, lobby=None, music_on="Off"):
        self.server_socket = None
        self.server_ip = SERVER_ADDRESS
        self.server_port = TCP_PORT
        self.player_name = name
        self.connected = connected
        self.game_data = None
        self.running = running
        self.lobby_code = lobby
        self.music_on = music_on

        # GUI
        self.root = None
        self.status_label = None


    def connect_to_server(self, lobby):
        """Connect to server using lobby code"""
        # Store lobby code for potential restart
        self.lobby_code = lobby

        # Connect directly via TCP to the cloud server
        try:
            self.update_status(f"Connecting to server...")
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.connect((self.server_ip, self.server_port))

            # Send join message with lobby code
            self.send_message({
                "type": "join",
                "name": self.player_name,
                "lobby_code": lobby  # Server will route to correct lobby
            })

            self.connected = True
            self.update_status(f"Connected to lobby")

            # Start listening thread
            threading.Thread(target=self.listen_to_server, daemon=True).start()

            return True
        except Exception as e:
            self.update_status(f"Connection failed: {e}")
            return False


    def send_message(self, message):
        """Send JSON message to server"""
        try:
            self.server_socket.send(json.dumps(message).encode())
        except Exception as e:
            print(f"Error sending message: {e}")


    def listen_to_server(self):
        """Listen for messages from server"""
        while self.running and self.connected:
            try:
                data = self.server_socket.recv(BUFFER_SIZE).decode()
                if not data:
                    break

                message = json.loads(data)
                self.handle_server_message(message)
            except Exception as e:
                print(f"Error receiving message: {e}")
                break

        self.connected = False


    def handle_server_message(self, message):
        """Handle messages from server - MUST schedule UI updates on main thread"""
        msg_type = message.get("type")

        if msg_type == "join_success":
            updated_lobby_code = message.get("lobby_code")
            if updated_lobby_code:
                self.lobby_code = updated_lobby_code
            print(f"Successfully joined lobby {updated_lobby_code}")
            # Schedule article request on main thread
            if self.root:
                self.root.after(100, self.request_article)
        elif msg_type == "join_rejected":
            self.update_status(f"Failed to connect to {self.lobby_code}")
        elif msg_type == "game_start":
            start_article = message.get("start_article")
            end_article = message.get("end_article")
            print(f"Game starting: {start_article} -> {end_article}")

            # Schedule game start on main thread
            if self.root:
                self.root.after(100, lambda: self.start_game_callback(start_article, end_article))
        elif msg_type == "game_results":
            results = message.get("results")
            print("Received final results:", results)
            self.show_results(results)


    def start_game_callback(self, start_article, end_article):
        """Callback to start game on main thread"""
        # Close lobby window
        if self.root:
            self.root.destroy()
            self.root = None

        # Launch game
        self.play_game(start_article, end_article)


    def request_article(self):
        """Get article request from player"""
        # Close current window
        if self.root:
            self.root.destroy()
            self.root = None

        # Get article request from player
        article_request = clr.main(self.lobby_code)

        # Send to server
        self.send_message({
            "type": "article_request",
            "article": article_request if article_request else ""
        })

        # Show waiting screen
        self.show_waiting_screen()


    def play_game(self, start_article, end_article):
        """Play the game and send results to server"""
        # Launch game and get results
        game_result = clm.main(start_article, end_article, self.player_name, show_results_dialog=False)

        # Send results to server
        if game_result and self.connected:
            self.send_message({
                "type": "game_result",
                "status": game_result["status"],
                "clicks": game_result["clicks"],
                "time": game_result["time"],
                "articles": game_result["articles"]
            })

        # Create a root window to keep the event loop alive
        # while waiting for results from the server
        self.root = customtkinter.CTk()
        self.root.withdraw()  # Hide the window
        self.root.mainloop()


    def show_waiting_screen(self):
        """Show waiting screen while waiting for game to start"""
        self.root = customtkinter.CTk()
        self.root.title("Wikipedia Race - Client")
        self.root.geometry("400x300")

        customtkinter.CTkLabel(
            self.root,
            text="Waiting for game",
            font=("Arial", 20)
        ).pack()
        customtkinter.CTkLabel(
            self.root,
            text=self.lobby_code,
            font=("Arial", 30, "bold")
        ).pack()
        customtkinter.CTkLabel(
            self.root,
            text="to start...",
            font=("Arial", 20)
        ).pack()

        self.status_label = customtkinter.CTkLabel(
            self.root,
            text="Article request submitted",
            font=("Arial", 14)
        )
        self.status_label.pack(pady=20)

        customtkinter.CTkButton(
            self.root,
            text="Disconnect",
            command=lambda: [mixer.Sound("./button.mp3").play(), self.disconnect()],
            fg_color="red"
        ).pack(pady=20)

        self.root.protocol("WM_DELETE_WINDOW", self.disconnect)
        self.root.mainloop()


    def show_results(self, results):
        """Show final results screen"""
        results_window = customtkinter.CTk()
        results_window.title("Game Results")
        results_window.geometry("500x600")

        customtkinter.CTkLabel(
            results_window,
            text="Final Results",
            font=("Arial", 24, "bold")
        ).pack(pady=20)

        # Results display
        results_frame = customtkinter.CTkFrame(results_window)
        results_frame.pack(pady=20, padx=20, fill="both", expand=True)

        for result in results:
            result_text = f"#{result["rank"]} {result["name"]}      Score: {result.get("total_points", 0)}\n"
            result_text += f"   Status: {result["status"]} | Clicks: {result["clicks"]} | Time: {result["time"]:.1f}s\n"

            label = customtkinter.CTkLabel(
                results_frame,
                text=result_text,
                font=("Arial", 14),
                justify="left"
            )
            label.pack(pady=5, anchor="w", padx=10)

        # Buttons
        button_frame = customtkinter.CTkFrame(results_window)
        button_frame.pack(pady=20)


        def play_again():
            if self.connected:
                self.send_message({"type": "play_again"})

            results_window.destroy()

            # Restart
            self.root = None
            self.request_article()

        customtkinter.CTkButton(
            button_frame,
            text="Play Again",
            command=lambda: [mixer.Sound("./button.mp3").play(), play_again()],
            font=("Arial", 16)
        ).pack(side="left", padx=10)
        customtkinter.CTkButton(
            button_frame,
            text="Quit",
            command=lambda: [mixer.Sound("./button.mp3").play(),
                             self.disconnect(),
                             results_window.destroy()],
            fg_color="red",
            font=("Arial", 16)
        ).pack(side="left", padx=10)
        results_window.protocol("WM_DELETE_WINDOW", lambda: [self.disconnect(), results_window.destroy()])
        results_window.mainloop()


    def update_status(self, message):
        """Update status label"""
        print(message)
        if self.status_label and self.root:
            try:
                self.root.after(0, lambda: self.status_label.configure(text=message))
            except:
                pass


    def disconnect(self):
        """Disconnect from server"""
        self.running = False
        self.connected = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        if self.root:
            try:
                self.root.destroy()
            except:
                pass


    def manage_music(self, check_var):
        self.music_on = check_var.get()
        if check_var.get() == "On":
            try:
                music = mixer.Sound("music.mp3")
                music.play(-1)
            except Exception as e:
                print(e)
                self.music_on = "Off"
        else:
            mixer.stop()


    def start(self):
        """Start the client and show join screen"""
        customtkinter.set_appearance_mode("System")
        try:
            customtkinter.set_default_color_theme("blue")
        except:
            pass

        self.root = customtkinter.CTk()
        self.root.title("Wikipedia Race - Join Game")
        self.root.geometry("400x400")

        mixer.init()

        customtkinter.CTkLabel(
            self.root,
            text="Join Wikipedia Race",
            font=("Arial", 24, "bold")
        ).pack(pady=20)

        # Enable/disable music
        check_var = customtkinter.StringVar(value=self.music_on)
        self.manage_music(check_var)
        checkbox = customtkinter.CTkCheckBox(
            self.root,
            text="Music",
            variable=check_var,
            command=lambda: self.manage_music(check_var),
            onvalue="On",
            offvalue="Off"
        )
        checkbox.place(relx=0.9, rely=0.9, anchor=customtkinter.CENTER)
        
        # Player name
        customtkinter.CTkLabel(
            self.root,
            text="Your Name:",
            font=("Arial", 14)
        ).pack(pady=5)
        name_entry = customtkinter.CTkEntry(
            self.root, width=250,
            placeholder_text="Enter your name"
        )
        name_entry.pack(pady=5)

        # Pre-fill if provided
        if self.player_name:
            name_entry.insert(0, self.player_name)

        # Lobby code
        customtkinter.CTkLabel(
            self.root,
            text="Lobby Code:",
            font=("Arial", 14)
        ).pack(pady=5)
        code_entry = customtkinter.CTkEntry(
            self.root,
            width=250,
            placeholder_text="Enter 4-digit code"
        )
        code_entry.pack(pady=5)

        # Pre-fill if provided
        if self.lobby_code:
            code_entry.insert(0, self.lobby_code)

        self.status_label = customtkinter.CTkLabel(
            self.root,
            text=f"Server: {SERVER_ADDRESS}",
            font=("Arial", 12),
            text_color="gray"
        )
        self.status_label.pack(pady=10)

        def join_game(lobby=None):
            self.player_name = name_entry.get().strip()
            if lobby is None:
                lobby = code_entry.get().strip().upper()

            if not self.player_name:
                self.update_status("Please enter your name")
                return
            if not lobby:
                self.update_status("Please enter lobby code")
                return

            self.connect_to_server(lobby)

        customtkinter.CTkButton(
            self.root,
            text="Join Game",
            command=lambda: [mixer.Sound("./button.mp3").play(), join_game()],
            font=("Arial", 16)
        ).pack(pady=10)
        customtkinter.CTkButton(
            self.root,
            text="New Game",
            command=lambda: [mixer.Sound("./button.mp3").play(), join_game("NG")],
            font=("Arial", 16)
        ).pack(pady=10)

        self.root.protocol("WM_DELETE_WINDOW", self.disconnect)

        # If both player name and lobby code are provided, auto-connect
        if self.player_name and self.lobby_code:
            self.root.after(20, lambda: join_game(self.lobby_code))

        self.root.mainloop()


if __name__ == "__main__":
    # Check if player name and lobby code were passed as arguments
    if len(sys.argv) >= 4:
        player_name = sys.argv[-3]
        lobby_code = sys.argv[-2]
        music_setting = sys.argv[-1]
        client = WikiRaceClient(name=player_name, lobby=lobby_code, music_on=music_setting)
    else:
        client = WikiRaceClient(name=None, lobby=None, music_on="Off")

    client.start()
