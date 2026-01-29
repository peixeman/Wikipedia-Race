import customtkinter
from mediawikiapi import MediaWikiAPI
from pygame import mixer
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
import time


def display_game_stats(window, state):
    game_result = customtkinter.CTkLabel(
        window,
        text=f"Game result: {state.game_status}",
        text_color="black",
        font=("Arial", 25)
    )
    game_result.place(relx=0.5, rely=0.35, anchor=customtkinter.CENTER)
    num_clicks = len(state.articles_navigated) - 1
    total_clicks = customtkinter.CTkLabel(
        window,
        text=f"Total clicks: {num_clicks}",
        text_color="black",
        font=("Arial", 25)
    )
    total_clicks.place(relx=0.5, rely=0.45, anchor=customtkinter.CENTER)
    game_time_length = "Game time: "
    if int(round(state.game_duration) // 60) > 0:
        game_time_length += f"{int(round(state.game_duration) // 60)} m : {int(round(state.game_duration) % 60)} s"
    else:
        game_time_length += f"{round(state.game_duration, 1)} s"
    game_time = customtkinter.CTkLabel(
        window,
        text=game_time_length,
        text_color="black",
        font=("Arial", 25)
    )
    game_time.place(relx=0.5, rely=0.55, anchor=customtkinter.CENTER)
    try:
        avg_time_per_article = round(state.game_duration / num_clicks, 2)
    except ZeroDivisionError:
        avg_time = customtkinter.CTkLabel(
            window,
            text="Average time per article not available",
            text_color="black",
            font=("Arial", 25)
        )
    else:
        avg_time = customtkinter.CTkLabel(
            window,
            text=f"Average time per article: {avg_time_per_article} s",
            text_color="black",
            font=("Arial", 25)
        )
    finally:
        avg_time.place(relx=0.5, rely=0.65, anchor=customtkinter.CENTER)
    close_button = customtkinter.CTkButton(
        window,
        text="Close",
        command=lambda: [mixer.Sound("./button.mp3").play(),
                         window.destroy()]
    )
    close_button.place(relx=0.5, rely=0.9, anchor=customtkinter.CENTER)

    window.mainloop()

    return


def display_stop_watch(seconds):
    if int(round(seconds) // 60) > 0 and int(round(seconds) % 60) >= 10:
        return f"{int(round(seconds) // 60)}:{int(round(seconds) % 60)}"
    elif int(round(seconds)) > 59:
        return f"{int(round(seconds) // 60)}:0{int(round(seconds) % 60)}"
    return str(int(round(seconds)))

def show_hint(window, article, button):
    mediawikiapi = MediaWikiAPI()
    hint_text = mediawikiapi.summary(article).replace("\n", "\n\n")
    hint = customtkinter.CTkTextbox(
        window,
        width=480,
        height=220,
        wrap="word",
        font=("Arial", 15),
    )
    hint.insert(index="1.0", text=hint_text)
    hint.place(relx=0.39, rely=0.7, anchor=customtkinter.CENTER)
    hint.configure(state="disabled")
    button.configure(state="disabled")


def fold(game):
    game.game_status = "Fold"


def disable_search_bar(driver):
    """Disable the Wikipedia search bar to prevent cheating"""
    try:
        # JavaScript to disable search inputs and hide search suggestions
        script = """
        // Disable all search inputs
        var searchInputs = document.querySelectorAll('input[name="search"]');
        searchInputs.forEach(function(input) {
            input.disabled = true;
            input.style.opacity = '0.5';
            input.placeholder = 'Search disabled during game';
        });

        // Hide search suggestions
        var searchSuggestions = document.querySelector('.suggestions');
        if (searchSuggestions) {
            searchSuggestions.style.display = 'none';
        }

        // Disable search buttons
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
    """Class to hold mutable game state"""
    def __init__(self):
        self.game_status = "Running"
        self.last_url = None
        self.articles_navigated = []
        self.game_duration = 0


def game_loop(driver, root, game_state, end_article, initial_time, stop_watch_label):
    if game_state.game_status != "Running":
        # Game ended, stop the loop and close window
        end_time = time.time()
        game_state.game_duration = end_time - initial_time

        driver.quit()
        root.quit()
        return

    # Update label
    stop_watch_label.configure(text=display_stop_watch(time.time() - initial_time))

    current_url = driver.current_url
    if current_url != game_state.last_url:
        game_state.last_url = current_url
        if driver.title.replace(" - Wikipedia", "") != end_article:
            game_state.articles_navigated.append(driver.title.replace(" - Wikipedia", ""))

    driver.wait = WebDriverWait(driver, 10)
    if "wikipedia" not in driver.title.lower() and driver.title != "":
        print("Player navigated away")
        game_state.game_status = "Forfeit"

    if len(driver.window_handles) > 1:
        print("Player has too many windows open")
        game_state.game_status = "Forfeit"

    if driver.title.replace(" - Wikipedia", "") == end_article:
        game_state.articles_navigated.append("[ >> ] " + driver.title.replace(" - Wikipedia", "") + " [ << ]")
        print("Player won")
        game_state.game_status = "Win"

    # Attempt to prevent cheating by internal searching
    disable_search_bar(driver)

    try:
        root.after(1000, game_loop, driver, root, game_state, end_article, initial_time, stop_watch_label)
    except Exception as e:
        print(e)


def main(start_article, end_article, player_name, show_results_dialog=True):
    # Setup
    customtkinter.set_appearance_mode("System")  # Modes: system (default), light, dark
    customtkinter.set_default_color_theme("blue")  # Themes: blue (default), dark-blue, green
    root = customtkinter.CTk()
    root.geometry("720x480")
    root.title(f"Client - {player_name}")
    root.resizable(False, False)

    mediawiki = MediaWikiAPI()
    driver = webdriver.Firefox()

    # Information console dialog
    print(start_article + " --> " + end_article)

    # Open starting article with Selenium
    try:
        driver.get(mediawiki.page(start_article).url)
    except Exception as e:
        print(e)
        driver.close()
        raise SystemExit(-1)
    else:
        assert len(driver.window_handles) == 1

    game_state = GameState()
    game_state.articles_navigated = ["[ << ] " + driver.title.replace(" - Wikipedia", "") + " [ >> ]"]
    game_state.last_url = driver.current_url
    initial_time = time.time()

    target_frame = customtkinter.CTkFrame(
        root,
        width=640,
        height=120
    )
    target_frame.place(relx=0.5, rely=0.3, anchor=customtkinter.CENTER)
    target_text = customtkinter.CTkLabel(
        target_frame,
        text=f"Find the article:",
        text_color="black",
        font=("Arial", 30)
    )
    target_text.place(relx=0.5, rely=0.3, anchor=customtkinter.CENTER)
    target_article_info = customtkinter.CTkLabel(
        target_frame,
        text=end_article,
        text_color="black",
        font=("Arial", 40, "bold")
    )
    target_article_info.place(relx=0.5, rely=0.65, anchor=customtkinter.CENTER)
    stop_watch_frame = customtkinter.CTkFrame(
        root,
        width=100,
        height=100,
        fg_color="snow",
        border_color="gray",
        border_width=5,
        corner_radius=50
    )
    stop_watch_frame.place(relx=0.85, rely=0.6, anchor=customtkinter.CENTER)
    stop_watch = customtkinter.CTkLabel(
        stop_watch_frame,
        text=display_stop_watch(time.time() - initial_time),
        text_color="black",
        font=("Arial", 25)
    )
    stop_watch.place(relx=0.5, rely=0.5, anchor=customtkinter.CENTER)
    hint_button = customtkinter.CTkButton(
        root,
        text="Hint",
        command=lambda: [mixer.Sound("./button.mp3").play(),
                         show_hint(root, end_article, hint_button)]
    )
    hint_button.place(relx=0.85, rely=0.8, anchor=customtkinter.CENTER)
    fold_button = customtkinter.CTkButton(
        root,
        text="Fold",
        fg_color="red",
        command=lambda: [mixer.Sound("./button.mp3").play(),
                         fold(game_state)]
    )
    fold_button.place(relx=0.85, rely=0.9, anchor=customtkinter.CENTER)

    root.after(1000, game_loop, driver, root, game_state, end_article, initial_time, stop_watch)
    root.mainloop()

    root.destroy()

    # Only show results dialog if not in network mode
    if show_results_dialog:
        results_dialog = customtkinter.CTk()
        results_dialog.geometry("400x240")
        results_dialog.title("Results")
        display_game_stats(results_dialog, game_state)
        results_dialog.mainloop()

    return {
        "status": game_state.game_status,
        "clicks": len(game_state.articles_navigated) - 1,
        "time": game_state.game_duration,
        "articles": game_state.articles_navigated
    }


if __name__ == "__main__":
    mixer.init()
    main("","", "", show_results_dialog=True)
