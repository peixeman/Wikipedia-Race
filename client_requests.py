import customtkinter
from mediawikiapi import MediaWikiAPI
from pygame import mixer

def main(lobby_code):
    mixer.init()

    customtkinter.set_appearance_mode("System")  # Modes: system (default), light, dark
    customtkinter.set_default_color_theme("blue")  # Themes: blue (default), dark-blue, green

    req_root = customtkinter.CTk()
    req_root.geometry("400x240")
    req_root.title(f"Submit an article ({lobby_code})")

    result = {  "suggestion": None  }


    def button_function():
        suggestion = text_box.get()
        result["suggestion"] = suggestion.strip()
        req_root.destroy()

    def random_button_function():
        mediawikiapi = MediaWikiAPI()
        result["suggestion"] = mediawikiapi.random(1)
        req_root.destroy()


    info_text_frame = customtkinter.CTkFrame(
        req_root,
        width=360,
        height=70
    )
    info_text_frame.place(relx=0.5, rely=0.25, anchor=customtkinter.CENTER)
    info_text = customtkinter.CTkLabel(
        info_text_frame,
        text="Enter a Wikipedia article\nClick \"Submit\" to skip or submit your article",
        font=("Arial", 18),
        fg_color="transparent",
        textvariable=""
    )
    info_text.place(relx=0.5, rely=0.5, anchor=customtkinter.CENTER)
    text_box = customtkinter.CTkEntry(master=req_root, placeholder_text="Enter article title")
    text_box.place(relx=0.5, rely=0.5, anchor=customtkinter.CENTER)
    submit_button = customtkinter.CTkButton(master=req_root, text="Submit", command=lambda: [mixer.Sound("./button.mp3").play(),
                                                                                             button_function()])
    submit_button.place(relx=0.5, rely=0.65, anchor=customtkinter.CENTER)
    random_button = customtkinter.CTkButton(
        master=req_root,
        text="Random (Hard, click Submit to skip!)",
        fg_color="red",
        command=lambda: [mixer.Sound("./button.mp3").play(),
                         random_button_function()]
    )
    random_button.place(relx=0.5, rely=0.8, anchor=customtkinter.CENTER)

    req_root.mainloop()

    return result["suggestion"]


if __name__ == "__main__":
    main(lobby_code="")
