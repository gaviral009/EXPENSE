import sys
print(sys.executable)
import customtkinter as ctk
from PIL import Image
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
root = ctk.CTk()
root.geometry("1524x784")
root.title("Expense Tracker")
left_frame = ctk.CTkFrame(root, corner_radius=0)
left_frame.pack(side="left", fill="both", expand=True)
original_img = Image.open("bg.jpg")
img_label = ctk.CTkLabel(left_frame, text="")
img_label.place(x=0, y=0, relwidth=1, relheight=1)
def resize_image(event):
    new_width = event.width
    new_height = event.height
    resized = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    new_img = ctk.CTkImage(resized, size=(new_width, new_height))
    img_label.configure(image=new_img)
    img_label.image = new_img
left_frame.bind("<Configure>", resize_image)
right_frame = ctk.CTkFrame(root, fg_color="#0d0d0d")
right_frame.pack(side="right", fill="both", expand=True)
logo_img = ctk.CTkImage(Image.open("final logo.png"), size=(222,87))
def show_login():
    signup_frame.pack_forget()
    login_frame.pack(fill="both", expand=True)
def show_signup():
    login_frame.pack_forget()
    signup_frame.pack(fill="both", expand=True)
login_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
login_container = ctk.CTkFrame(login_frame, fg_color="transparent")
login_container.place(relx=0.5, rely=0.5, anchor="center")
logo_label_login = ctk.CTkLabel(login_container, image=logo_img, text="")
logo_label_login.pack(pady=(0, 10))
ctk.CTkLabel(login_container, text="Sign in", font=("Arial", 28)).pack(pady=10)
username = ctk.CTkEntry(login_container, width=300, height=40, placeholder_text="Username")
username.pack(pady=10)
password = ctk.CTkEntry(login_container, width=300, height=40, show="*", placeholder_text="Password")
password.pack(pady=10)
login_btn = ctk.CTkButton(login_container, text="Login", width=300, height=45, corner_radius=25)
login_btn.pack(pady=15)
create_btn = ctk.CTkButton(
    login_container,
    text="Create Account",
    width=300,
    height=45,
    fg_color="transparent",
    border_width=1,
    corner_radius=25,
    command=show_signup)
create_btn.pack(pady=10)
signup_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
signup_container = ctk.CTkFrame(signup_frame, fg_color="transparent")
signup_container.place(relx=0.5, rely=0.5, anchor="center")
logo_label_signup = ctk.CTkLabel(signup_container, image=logo_img, text="")
logo_label_signup.pack(pady=(0, 10))
ctk.CTkLabel(signup_container, text="Create Account", font=("Arial", 28)).pack(pady=10)
new_user = ctk.CTkEntry(signup_container, width=300, height=40, placeholder_text="Username")
new_user.pack(pady=10)
new_pass = ctk.CTkEntry(signup_container, width=300, height=40, show="*", placeholder_text="Password")
new_pass.pack(pady=10)
confirm_pass = ctk.CTkEntry(signup_container, width=300, height=40, show="*", placeholder_text="Confirm Password")
confirm_pass.pack(pady=10)
create_account_btn = ctk.CTkButton(
    signup_container,
    text="Create Account",
    width=300,
    height=45,
    corner_radius=25)
create_account_btn.pack(pady=15)
back_btn = ctk.CTkButton(
    signup_container,
    text="Back to Login",
    width=300,
    height=45,
    fg_color="transparent",
    border_width=1,
    corner_radius=25,
    command=show_login)
back_btn.pack(pady=10)
login_frame.pack(fill="both", expand=True)
root.mainloop()