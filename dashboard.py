import customtkinter as ctk
from PIL import Image
win=ctk.CTk()
win.geometry('1524x784+0+0')
win.resizable(False,False)
img = ctk.CTkImage(light_image=Image.open("img.png"),size=(1524,784))
label = ctk.CTkLabel(win, image=img,text='')
label.place(x=0,y=0)
fra=ctk.CTkFrame(win,width=1524,height=784,fg_color='transparent',bg_color='transparent')
fra.pack(fill="both",expand=True)
fra.place(x=0,y=0)
dash=ctk.CTkLabel(win,text='Dashboard',font=('Segoe UI',50),fg_color='transparent',text_color='#00ABFF')
dash.grid(padx=50,pady=10)
win.mainloop()