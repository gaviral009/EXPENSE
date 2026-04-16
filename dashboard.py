import customtkinter as ctk
from PIL import Image
win=ctk.CTk()
win.geometry('1524x784+0+0')
img = ctk.CTkImage(light_image=Image.open("img.png"),size=(184,184))
label = ctk.CTkLabel(win, image=img,text='')
label.pack(pady=20)
dash=ctk.CTkLabel(win,text='Dashboard',font=('Helvetica',50,'bold'))
dash.pack()
win.mainloop()