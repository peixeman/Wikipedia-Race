import customtkinter
from mediawikiapi import MediaWikiAPI
from pygame import mixer


class ArticleRequestFrame(customtkinter.CTkFrame):
    def __init__(self, master, lobby_code, on_submit):
        super().__init__(master)
        self.lobby_code = lobby_code
        self.on_submit = on_submit

        self.mediawiki = MediaWikiAPI()

        self.grid_rowconfigure((0, 1, 2, 3), weight=1)
        self.grid_columnconfigure(0, weight=1)

        title = customtkinter.CTkLabel(
            self,
            text=f"Submit an article ({lobby_code})",
            font=("Arial", 22, "bold")
        )
        title.grid(row=0, column=0, pady=(20, 10))

        info = customtkinter.CTkLabel(
            self,
            text="Enter a Wikipedia article\nClick Submit to skip or submit your article",
            font=("Arial", 16),
        )
        info.grid(row=1, column=0, pady=10)

        self.text_box = customtkinter.CTkEntry(self, placeholder_text="Enter article title", width=280)
        self.text_box.grid(row=2, column=0, pady=10)

        submit_button = customtkinter.CTkButton(
            self,
            text="Submit",
            command=self._submit
        )
        submit_button.grid(row=3, column=0, pady=(10, 6))

        random_button = customtkinter.CTkButton(
            self,
            text="Random (Hard, click Submit to skip!)",
            fg_color="red",
            command=self._random
        )
        random_button.grid(row=4, column=0, pady=(0, 20))


    def _submit(self):
        mixer.Sound("./button.mp3").play()
        suggestion = self.text_box.get().strip()
        self.on_submit(suggestion)


    def _random(self):
        mixer.Sound("./button.mp3").play()
        suggestion = self.mediawiki.random(1)
        self.on_submit(suggestion)
