import customtkinter
import json
from pygame import mixer
import socket
import sys
import threading

from client_requests_frame import ArticleRequestFrame
from client_main import GameFrame

SERVER_ADDRESS = "metro.proxy.rlwy.net"
TCP_PORT = 30825
BUFFER_SIZE = 4096


class WikiRaceClient:
    def __init__(self):
        self.server_socket = None
        self.server_ip = SERVER_ADDRESS
        self.server_port = TCP_PORT

        self.player_name = None
        self.lobby_code = None
        self.music_on = "Off"

        self.connected = False
        self.running = True

        self.root = None
        self.current_frame = None
        self.status_label = None

        self.player_count_label = None
        self.player_count = 1


    # UI helpers
    def show_frame(self, frame):
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = frame
        self.current_frame.place(relwidth=1, relheight=1)


    def update_status(self, msg):
        print(msg)
        if self.status_label and self.root:
            self.root.after(0, lambda: self.status_label.configure(text=msg))


    def update_player_count_label(self):
        if self.player_count_label and self.root:
            text = f"{self.player_count} player"
            if self.player_count != 1:
                text += "s"
            text += " in lobby"
            self.root.after(0, lambda: self.player_count_label.configure(text=text))


    # Networking
    def send_message(self, message):
        try:
            self.server_socket.send(json.dumps(message).encode())
        except Exception as e:
            print(f"Error sending message: {e}")


    def connect_to_server(self, lobby):
        self.lobby_code = lobby
        try:
            self.update_status("Connecting to server...")
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.connect((self.server_ip, self.server_port))

            self.send_message({
                "type": "join",
                "name": self.player_name,
                "lobby_code": lobby
            })
        except Exception as e:
            self.update_status(f"Connection failed: {e}")
            return False
        else:
            self.connected = True
            threading.Thread(target=self.listen_to_server, daemon=True).start()
            return True


    def listen_to_server(self):
        while self.running and self.connected:
            try:
                data = self.server_socket.recv(BUFFER_SIZE).decode()
                if not data:
                    break
                message = json.loads(data)
                self.root.after(0, lambda m=message: self.handle_server_message(m))
            except Exception as e:
                self.update_status("Error in server communication")
                print(f"Error receiving message: {e}")
                break
        self.connected = False


    def handle_server_message(self, message):
        msg_type = message.get("type")

        if msg_type == "join_success":
            self.update_status("Connected to lobby")
            updated_lobby_code = message.get("lobby_code")
            if updated_lobby_code:
                self.lobby_code = updated_lobby_code
            self.show_article_request()

        elif msg_type == "join_rejected":
            self.update_status(f"Failed to connect to {self.lobby_code}")

        elif msg_type == "game_start":
            start_article = message.get("start_article")
            end_article = message.get("end_article")
            self.start_game(start_article, end_article)

        elif msg_type == "receive_player_count":
            self.player_count = int(message.get("player_count"))
            # Update waiting screen
            self.update_player_count_label()

        elif msg_type == "game_results":
            results = message.get("results")
            self.show_results(results)


    # Screen management
    def show_join_screen(self):
        frame = customtkinter.CTkFrame(self.root)
        frame.place(relwidth=1, relheight=1)

        customtkinter.CTkLabel(frame, text="Join Wikipedia Race", font=("Arial", 24, "bold")).pack(pady=20)

        check_var = customtkinter.StringVar(value=self.music_on)
        checkbox = customtkinter.CTkCheckBox(
            frame,
            text="Music",
            variable=check_var,
            command=lambda: self.manage_music(check_var),
            onvalue="On",
            offvalue="Off"
        )
        checkbox.place(relx=0.9, rely=0.9, anchor=customtkinter.CENTER)

        customtkinter.CTkLabel(frame, text="Your Name:", font=("Arial", 14)).pack(pady=5)
        name_entry = customtkinter.CTkEntry(frame, width=250, placeholder_text="Enter your name")
        name_entry.pack(pady=5)
        if self.player_name:
            name_entry.insert(0, self.player_name)

        customtkinter.CTkLabel(frame, text="Lobby Code:", font=("Arial", 14)).pack(pady=5)
        code_entry = customtkinter.CTkEntry(frame, width=250, placeholder_text="Enter 4-digit code")
        code_entry.pack(pady=5)
        if self.lobby_code:
            code_entry.insert(0, self.lobby_code)

        self.status_label = customtkinter.CTkLabel(frame, text=f"Server: {SERVER_ADDRESS}", font=("Arial", 12), text_color="gray")
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


        customtkinter.CTkButton(frame, text="Join Game", command=lambda: [mixer.Sound("./button.mp3").play(), join_game()], font=("Arial", 16)).pack(pady=10)
        customtkinter.CTkButton(frame, text="New Game", command=lambda: [mixer.Sound("./button.mp3").play(), join_game("NG")], font=("Arial", 16)).pack(pady=10)

        self.show_frame(frame)

        if self.player_name and self.lobby_code:
            self.root.after(20, lambda: join_game(self.lobby_code))


    def show_article_request(self):
        def on_submit(article):
            self.send_message({"type": "article_request", "article": article if article else ""})
            self.show_waiting_screen()


        frame = ArticleRequestFrame(self.root, self.lobby_code, on_submit)
        self.show_frame(frame)


    def show_waiting_screen(self):
        frame = customtkinter.CTkFrame(self.root)

        customtkinter.CTkLabel(frame, text="Waiting for game", font=("Arial", 20)).pack()
        customtkinter.CTkLabel(frame, text=self.lobby_code, font=("Arial", 30, "bold")).pack()
        customtkinter.CTkLabel(frame, text="to start...", font=("Arial", 20)).pack()
        self.player_count_label = customtkinter.CTkLabel(frame, text=f"Please wait...", font=("Arial", 20))
        self.player_count_label.pack()

        self.status_label = customtkinter.CTkLabel(frame, text="Article request submitted", font=("Arial", 14))
        self.status_label.pack(pady=20)

        customtkinter.CTkButton(
            frame,
            text="Disconnect",
            command=lambda: [mixer.Sound("./button.mp3").play(), self.disconnect()],
            fg_color="red"
        ).pack(pady=20)

        self.show_frame(frame)


    def show_early_completion_screen(self):
        frame = customtkinter.CTkFrame(self.root)

        customtkinter.CTkLabel(frame, text="Waiting for players to complete", font=("Arial", 20)).pack(pady=50)

        customtkinter.CTkButton(
            frame,
            text="Disconnect",
            command=lambda: [mixer.Sound("./button.mp3").play(), self.disconnect()],
            fg_color="red"
        ).pack(pady=20)

        self.show_frame(frame)


    def start_game(self, start_article, end_article):
        def on_finish(game_result):
            # Send results
            if self.connected:
                self.send_message({
                    "type": "game_result",
                    "status": game_result["status"],
                    "clicks": game_result["clicks"],
                    "time": game_result["time"],
                    "articles": game_result["articles"]
                })
            # Return to waiting
            self.show_early_completion_screen()


        frame = GameFrame(self.root, start_article, end_article, self.player_name, on_finish)
        self.show_frame(frame)

    def show_results(self, results):
        frame = customtkinter.CTkFrame(self.root)

        customtkinter.CTkLabel(frame, text="Final Results", font=("Arial", 24, "bold")).pack(pady=20)
        results_frame = customtkinter.CTkFrame(frame)
        results_frame.pack(pady=20, padx=20, fill="both", expand=True)

        for result in results:
            result_text = f"#{result["rank"]} {result["name"]}      Score: {result.get("total_points", 0)}\n"
            result_text += f"   Status: {result["status"]} | Clicks: {result["clicks"]} | Time: {result["time"]:.1f}s\n"

            customtkinter.CTkLabel(results_frame, text=result_text, font=("Arial", 14), justify="left").pack(
                pady=5, anchor="w", padx=10
            )

        button_frame = customtkinter.CTkFrame(frame)
        button_frame.pack(pady=20)


        def play_again():
            if self.connected:
                self.send_message({"type": "play_again"})
            self.show_article_request()


        customtkinter.CTkButton(
            button_frame,
            text="Play Again",
            command=lambda: [mixer.Sound("./button.mp3").play(), play_again()],
            font=("Arial", 16)
        ).pack(side="left", padx=10)

        customtkinter.CTkButton(
            button_frame,
            text="Quit",
            command=lambda: [mixer.Sound("./button.mp3").play(), self.disconnect()],
            fg_color="red",
            font=("Arial", 16)
        ).pack(side="left", padx=10)

        self.show_frame(frame)


    def manage_music(self, check_var):
        self.music_on = check_var.get()
        if self.music_on == "On":
            try:
                music = mixer.Sound("music.mp3")
                music.play(-1)
            except Exception as e:
                print(e)
                self.music_on = "Off"
        else:
            mixer.stop()


    def disconnect(self):
        self.running = False
        self.connected = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        if self.root:
            self.root.quit()
            self.root.destroy()
            sys.exit()


    def start(self):
        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")
        mixer.init()

        self.root = customtkinter.CTk()
        self.root.title("Wikipedia Race - Client")
        self.root.geometry("400x400")
        self.root.protocol("WM_DELETE_WINDOW", self.disconnect)

        self.show_join_screen()
        self.root.mainloop()


if __name__ == "__main__":
    client = WikiRaceClient()
    client.start()
