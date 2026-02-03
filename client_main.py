import customtkinter
from mediawikiapi import MediaWikiAPI
from pygame import mixer
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
import time


def display_stop_watch(seconds):
    if int(round(seconds) // 60) > 0 and int(round(seconds) % 60) >= 10:
        return f"{int(round(seconds) // 60)}:{int(round(seconds) % 60)}"
    elif int(round(seconds)) > 59:
        return f"{int(round(seconds) // 60)}:0{int(round(seconds) % 60)}"
    return str(int(round(seconds)))


def disable_search_bar(driver):
    try:
        script = """
        var searchInputs = document.querySelectorAll('input[name="search"]');
        searchInputs.forEach(function(input) {
            input.disabled = true;
            input.style.opacity = '0.5';
            input.placeholder = 'Search disabled during game';
        });
        var searchSuggestions = document.querySelector('.suggestions');
        if (searchSuggestions) {
            searchSuggestions.style.display = 'none';
        }
        var searchButtons = document.querySelectorAll('button[type="submit"]');
        searchButtons.forEach(function(button) {
            if (button.closest('form')?.querySelector('input[name="search"]')) {
                button.disabled = true;
            }
        });
        """
        driver.execute_script(script)
    except Exception as e:
        print(f"Could not disable search bar: {e}")


class GameState:
    def __init__(self):
        self.game_status = "Running"
        self.last_url = None
        self.articles_navigated = []
        self.game_duration = 0


class GameFrame(customtkinter.CTkFrame):
    """Game UI is mounted to existing CTkFrame"""
    def __init__(self, master, start_article, end_article, player_name, on_finish):
        super().__init__(master)
        self.start_article = start_article
        self.end_article = end_article
        self.player_name = player_name
        self.on_finish = on_finish

        self.mediawiki = MediaWikiAPI()
        self.driver = None
        self.game_state = GameState()
        self.initial_time = None

        self._build_ui()
        self._start_browser_and_game()


    def _build_ui(self):
        self.place(relwidth=1, relheight=1)

        self.master.geometry("720x480")
        self.master.title(f"Client - {self.player_name}")
        self.master.resizable(False, False)

        self.target_frame = customtkinter.CTkFrame(self, width=640, height=120)
        self.target_frame.place(relx=0.5, rely=0.3, anchor=customtkinter.CENTER)

        self.target_text = customtkinter.CTkLabel(
            self.target_frame,
            text="Find the article:",
            text_color="black",
            font=("Arial", 30)
        )
        self.target_text.place(relx=0.5, rely=0.3, anchor=customtkinter.CENTER)

        self.target_article_info = customtkinter.CTkLabel(
            self.target_frame,
            text=self.end_article,
            text_color="black",
            font=("Arial", 40, "bold")
        )
        self.target_article_info.place(relx=0.5, rely=0.65, anchor=customtkinter.CENTER)

        self.stop_watch_frame = customtkinter.CTkFrame(
            self,
            width=100,
            height=100,
            fg_color="snow",
            border_color="gray",
            border_width=5,
            corner_radius=50
        )
        self.stop_watch_frame.place(relx=0.85, rely=0.6, anchor=customtkinter.CENTER)

        self.stop_watch_label = customtkinter.CTkLabel(
            self.stop_watch_frame,
            text="0",
            text_color="black",
            font=("Arial", 25)
        )
        self.stop_watch_label.place(relx=0.5, rely=0.5, anchor=customtkinter.CENTER)

        self.hint_button = customtkinter.CTkButton(
            self,
            text="Hint",
            command=self._show_hint
        )
        self.hint_button.place(relx=0.85, rely=0.8, anchor=customtkinter.CENTER)

        self.fold_button = customtkinter.CTkButton(
            self,
            text="Fold",
            fg_color="red",
            command=self._fold
        )
        self.fold_button.place(relx=0.85, rely=0.9, anchor=customtkinter.CENTER)


    def _start_browser_and_game(self):
        self.driver = webdriver.Firefox()

        try:
            self.driver.get(self.mediawiki.page(self.start_article).url)
        except Exception as e:
            print(e)
            try:
                self.driver.quit()
            except:
                pass
            self._finish_game("Forfeit")
            return

        self.game_state.articles_navigated = ["[ << ] " + self.driver.title.replace(" - Wikipedia", "") + " [ >> ]"]
        self.game_state.last_url = self.driver.current_url
        self.initial_time = time.time()

        self.after(1000, self._game_loop)


    def _show_hint(self):
        mixer.Sound("./button.mp3").play()
        try:
            hint_text = self.mediawiki.summary(self.end_article).replace("\n", "\n\n")
        except Exception:
            hint_text = "Hint unavailable."

        hint = customtkinter.CTkTextbox(
            self,
            width=480,
            height=220,
            wrap="word",
            font=("Arial", 15)
        )
        hint.insert(index="1.0", text=hint_text)
        hint.place(relx=0.39, rely=0.7, anchor=customtkinter.CENTER)
        hint.configure(state="disabled")
        self.hint_button.configure(state="disabled")


    def _fold(self):
        mixer.Sound("./button.mp3").play()
        self.game_state.game_status = "Fold"


    def _finish_game(self, status=None):
        if status is not None:
            self.game_state.game_status = status

        end_time = time.time()
        self.game_state.game_duration = end_time - self.initial_time if self.initial_time else 0

        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

        result = {
            "status": self.game_state.game_status,
            "clicks": len(self.game_state.articles_navigated) - 1,
            "time": self.game_state.game_duration,
            "articles": self.game_state.articles_navigated
        }

        self.destroy()
        self.on_finish(result)


    def _game_loop(self):
        if self.game_state.game_status != "Running":
            self._finish_game()
            return

        elapsed = time.time() - self.initial_time
        self.stop_watch_label.configure(text=display_stop_watch(elapsed))

        current_url = self.driver.current_url
        if current_url != self.game_state.last_url:
            self.game_state.last_url = current_url
            if self.driver.title.replace(" - Wikipedia", "") != self.end_article:
                self.game_state.articles_navigated.append(self.driver.title.replace(" - Wikipedia", ""))

        self.driver.wait = WebDriverWait(self.driver, 10)

        if "wikipedia" not in self.driver.title.lower() and self.driver.title != "":
            self.game_state.game_status = "Forfeit"

        if len(self.driver.window_handles) > 1:
            self.game_state.game_status = "Forfeit"

        if self.driver.title.replace(" - Wikipedia", "") == self.end_article:
            self.game_state.articles_navigated.append("[ >> ] " + self.driver.title.replace(" - Wikipedia", "") + " [ << ]")
            self.game_state.game_status = "Win"

        disable_search_bar(self.driver)

        self.after(1000, self._game_loop)
